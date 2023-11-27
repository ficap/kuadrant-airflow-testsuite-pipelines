import kubernetes.client as k8s


def dot_to_dynaconf_env(dynaconf_env_prefix: str, config_lines: list[str]):
    kv = {
        f"{dynaconf_env_prefix}_{k.replace('.', '__')}": v
        for k, v in [line.split("=", maxsplit=1) for line in config_lines]
    }
    return kv


def dict_to_V1EnvVar_list(env: dict[str, str]) -> list[k8s.V1EnvVar]:
    return [k8s.V1EnvVar(name, value) for name, value in env.items()]
