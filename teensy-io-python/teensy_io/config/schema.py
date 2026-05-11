SUPPORTED_PIN_TYPES = {"digital_input", "digital_output", "pwm", "analog"}
SUPPORTED_EDGES = {"rising", "falling", "both"}
SUPPORTED_PULLS = {"floating", "none", "up", "pullup", "down", "pulldown"}
SUPPORTED_ENCODER_MODES = {"x1", "x2", "x4"}


def validate_config(config: dict) -> None:
    if not isinstance(config, dict):
        raise ValueError("config root must be a mapping")

    for name, spec in config.get("pins", {}).items():
        _require_mapping("pins", name, spec)
        pin_type = spec.get("type")
        if pin_type not in SUPPORTED_PIN_TYPES:
            raise ValueError(f"pins.{name}.type must be one of {sorted(SUPPORTED_PIN_TYPES)}")
        _require_int(spec, "physical_pin", f"pins.{name}")
        if pin_type == "digital_input" and spec.get("pull", "floating") not in SUPPORTED_PULLS:
            raise ValueError(f"pins.{name}.pull must be one of {sorted(SUPPORTED_PULLS)}")
        if pin_type == "pwm":
            _require_number(spec, "frequency", f"pins.{name}", required=False)
            duty = spec.get("initial_duty", 0.0)
            if not isinstance(duty, (int, float)) or duty < 0.0 or duty > 1.0:
                raise ValueError(f"pins.{name}.initial_duty must be between 0.0 and 1.0")
        if pin_type == "analog":
            samples = spec.get("samples", 1)
            if not isinstance(samples, int) or samples < 1 or samples > 255:
                raise ValueError(f"pins.{name}.samples must be between 1 and 255")

    for name, spec in config.get("inputs", {}).items():
        _require_mapping("inputs", name, spec)
        _require_int(spec, "physical_pin", f"inputs.{name}")
        if spec.get("pull", "floating") not in SUPPORTED_PULLS:
            raise ValueError(f"inputs.{name}.pull must be one of {sorted(SUPPORTED_PULLS)}")

    for name, spec in config.get("counters", {}).items():
        _require_mapping("counters", name, spec)
        if "pin" not in spec and "input" not in spec:
            raise ValueError(f"counters.{name} requires pin or input")
        if spec.get("edge", "rising") not in SUPPORTED_EDGES:
            raise ValueError(f"counters.{name}.edge must be one of {sorted(SUPPORTED_EDGES)}")

    for name, spec in config.get("encoders", {}).items():
        _require_mapping("encoders", name, spec)
        _require_int(spec, "pin_a", f"encoders.{name}")
        _require_int(spec, "pin_b", f"encoders.{name}")
        if spec.get("mode", "x4") not in SUPPORTED_ENCODER_MODES:
            raise ValueError(f"encoders.{name}.mode must be one of {sorted(SUPPORTED_ENCODER_MODES)}")


def _require_mapping(section: str, name: str, spec: object) -> None:
    if not isinstance(spec, dict):
        raise ValueError(f"{section}.{name} must be a mapping")


def _require_int(spec: dict, key: str, prefix: str) -> None:
    if not isinstance(spec.get(key), int):
        raise ValueError(f"{prefix}.{key} must be an integer")


def _require_number(spec: dict, key: str, prefix: str, *, required: bool = True) -> None:
    if key not in spec and not required:
        return
    if not isinstance(spec.get(key), (int, float)):
        raise ValueError(f"{prefix}.{key} must be a number")
