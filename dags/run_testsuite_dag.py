"""
Runs kuadrant testsuite container as a kubernetes pod
"""
import kubernetes.client as k8s

from datetime import datetime

from airflow.decorators import task, dag
from airflow.models import Param

from utils.utils import dict_to_V1EnvVar_list

params = {
    "testsuite_image": Param(
        default="quay.io/kuadrant/testsuite:unstable",
        description="Testsuite image to use"
    ),
    "kube_api": Param(
        type="string",
        default="",
        description="API URL of target Openshift cluster",
    ),
    "project": Param(
        default="multi-cluster-gateways",
        description="Openshift project to use for testing"
    ),
    "make_target": Param(
        default="mgc",
        description="Testsuite make target to invoke -- corresponds to test type"
    ),
    "dynaconf_settings": Param(
        default=['control_plane.spokes={local-cluster={}}'],
        type=["null", "array"],
        description="Additional dynaconf params separated by new line each in a format key.subkey=value"
    )
}


@dag(
    dag_id="kuadrant-test",
    schedule=None,
    start_date=datetime(2021, 1, 1),
    tags=["test"],
    params=params,
    doc_md=__doc__,
    catchup=False,
)
def dag_run_testsuite():
    from airflow.providers.cncf.kubernetes.secret import Secret
    from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator

    @task(task_id="prepare-args")
    def prepare_args(**context):
        from utils.utils import dot_to_dynaconf_env
        params = context["params"]
        run_id = context["dag_run"].run_id

        env_vars = {"TARGET_KUBE_API": params["kube_api"]}

        dynaconf_env = dot_to_dynaconf_env("KUADRANT", params["dynaconf_settings"])
        dynaconf_env["KUADRANT_cluster__project"] = params["project"]
        dynaconf_env["KUADRANT_control_plane__hub__project"] = params["project"]

        env_vars.update(dynaconf_env)
        env_vars["MAKE_TARGET"] = params["make_target"]

        env_vars["junit"] = "true"  # generate a junit report file
        env_vars["RP_LAUNCH_NAME"] = run_id

        return [env_vars]

    testsuite_image_env = prepare_args().map(dict_to_V1EnvVar_list)
    secrets = [Secret("env", None, secret="airflow-kubeapi-creds"), Secret("env", None, secret="reportportal-creds")]
    resources = k8s.V1ResourceRequirements(limits={"cpu": "200m", "memory": "256Mi"})

    KubernetesPodOperator.partial(
        name="kuadrant-testsuite",
        image="{{ params.testsuite_image }}",
        cmds=["/bin/bash", "-c"],
        arguments=[
            'oc login "${TARGET_KUBE_API}" --username "${KUBE_USER}" --password "${KUBE_PASSWORD}" '
            '--insecure-skip-tls-verify=true && make ${MAKE_TARGET} || make reportportal'
        ],
        secrets=secrets,
        container_resources=resources,
        image_pull_policy="Always",
        task_id="run-testsuite",
        on_finish_action="delete_pod",
        hostnetwork=False,
    ).expand(env_vars=testsuite_image_env)


dag_run_testsuite()
