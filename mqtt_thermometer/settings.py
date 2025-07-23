from decimal import Decimal
from pathlib import Path
from typing import Tuple, Type

from pydantic import Field
from pydantic_extra_types.color import Color
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)


class MQTTBrokerSettings(BaseSettings):
    host: str = Field(default=...)
    port: int = Field(default=1883)


class SourceSettings(BaseSettings):
    label: str = Field(default=...)
    source: str = Field(default=...)
    calibration_multiplier: Decimal = Field(default=Decimal("1.0"))
    calibration_offset: Decimal = Field(default=Decimal("0.0"))
    border_color: Color = Field(default=...)
    background_color: Color = Field(default=...)


def _get_toml_file_path() -> Path:
    # Check if config path is provided via environment variable (for Docker)
    env_config_path = (
        Path.cwd() / "config" / "mqtt-thermometer.toml"
        if Path.cwd().name == "app"
        else None
    )
    if env_config_path and env_config_path.exists():
        return env_config_path

    # Check if we're running tests (look for test config first)
    import sys

    if any("pytest" in arg for arg in sys.argv) or "test" in sys.modules:
        test_config_path = (
            Path(__file__).parent.parent / "test" / "mqtt-thermometer.toml"
        )
        if test_config_path.exists():
            return test_config_path

    toml_file_name = "mqtt-thermometer.toml"
    file_path = Path(__file__).parent
    while file_path != file_path.root:
        potential_path = file_path.joinpath(toml_file_name)
        if potential_path.exists():
            return potential_path
        file_path = file_path.parent

    potential_path = Path(file_path.root).joinpath(toml_file_name)
    if potential_path.exists():
        return potential_path
    else:
        msg = f"Could not find {toml_file_name} in any parent directory"
        raise FileNotFoundError(msg)


class RootSettings(BaseSettings):
    application_name: str = Field(default="Thermometer")
    location: str = Field(default="Unknown")
    mqtt_broker: MQTTBrokerSettings = Field(default=...)
    db_connection_string: str = Field(
        default="data/mqtt-thermometer.db"
    )  # Default to data directory for Docker
    sources: list[SourceSettings] = Field(default=...)

    model_config = SettingsConfigDict(
        toml_file=_get_toml_file_path(),
        env_prefix="MQTT_THERMOMETER_",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (TomlConfigSettingsSource(settings_cls),)


settings = RootSettings()
