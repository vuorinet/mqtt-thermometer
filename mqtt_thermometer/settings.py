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


class RootSettings(BaseSettings):
    mqtt_broker: MQTTBrokerSettings = Field(default=...)
    db_connection_string: str = Field(default=...)
    sources: list[SourceSettings] = Field(default=...)

    model_config = SettingsConfigDict(
        toml_file=Path(__file__).parent.parent.joinpath("mqtt-thermometer.toml"),
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
