"""Sensor platform for Airthings BLE."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    EntityCategory,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfPressure,
    UnitOfSoundPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import AirthingsConfigEntry, AirthingsDataUpdateCoordinator
from .entity import AirthingsEntity
from .models import AirthingsSensorData

# Home Assistant doesn't ship a native radon unit constant usable as a
# SensorDeviceClass.RADON base unit at the time of writing; Bq/m3 is the
# scientifically standard unit and what the device reports natively, so
# entities are created directly in Bq/m3 with `suggested_unit_of_measurement`
# left to HA's unit-system conversion for pCi/L-preferring locales.
RADON_UNIT_BQ_M3 = "Bq/m³"


@dataclass(frozen=True, kw_only=True)
class AirthingsSensorEntityDescription(SensorEntityDescription):
    """Describes an Airthings sensor entity."""

    value_fn: Callable[[AirthingsSensorData], float | int | None]


SENSOR_DESCRIPTIONS: tuple[AirthingsSensorEntityDescription, ...] = (
    AirthingsSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.temperature,
    ),
    AirthingsSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.humidity,
    ),
    AirthingsSensorEntityDescription(
        key="pressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.pressure,
    ),
    AirthingsSensorEntityDescription(
        key="co2",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.co2,
    ),
    AirthingsSensorEntityDescription(
        key="voc",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.voc,
    ),
    AirthingsSensorEntityDescription(
        key="radon_1day_avg",
        translation_key="radon_1day_avg",
        device_class=SensorDeviceClass.RADON,
        native_unit_of_measurement=RADON_UNIT_BQ_M3,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.radon_1day_avg,
    ),
    AirthingsSensorEntityDescription(
        key="radon_longterm_avg",
        translation_key="radon_longterm_avg",
        device_class=SensorDeviceClass.RADON,
        native_unit_of_measurement=RADON_UNIT_BQ_M3,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.radon_longterm_avg,
    ),
    AirthingsSensorEntityDescription(
        key="radon_7day_avg",
        translation_key="radon_7day_avg",
        device_class=SensorDeviceClass.RADON,
        native_unit_of_measurement=RADON_UNIT_BQ_M3,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.radon_7day_avg,
    ),
    AirthingsSensorEntityDescription(
        key="radon_1year_avg",
        translation_key="radon_1year_avg",
        device_class=SensorDeviceClass.RADON,
        native_unit_of_measurement=RADON_UNIT_BQ_M3,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.radon_1year_avg,
    ),
    AirthingsSensorEntityDescription(
        key="illuminance",
        translation_key="illuminance",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.illuminance,
    ),
    AirthingsSensorEntityDescription(
        key="noise",
        translation_key="noise",
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.noise,
    ),
    AirthingsSensorEntityDescription(
        key="battery_percentage",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.battery_percentage,
    ),
    AirthingsSensorEntityDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement="V",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.battery_voltage,
    ),
    AirthingsSensorEntityDescription(
        key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.rssi,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirthingsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Airthings BLE sensors from a config entry.

    Entities are created only for fields the connected model actually
    populates (per the first successful sample), matching device
    capability instead of guessing from the model alone.
    """
    coordinator = entry.runtime_data
    sample = coordinator.data

    entities = [
        AirthingsSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
        if description.value_fn(sample) is not None
    ]
    async_add_entities(entities)


class AirthingsSensor(AirthingsEntity, SensorEntity):
    """A single Airthings sensor entity."""

    entity_description: AirthingsSensorEntityDescription

    def __init__(
        self,
        coordinator: AirthingsDataUpdateCoordinator,
        description: AirthingsSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}_{description.key}"

    @property
    def native_value(self) -> float | int | None:
        return self.entity_description.value_fn(self.coordinator.data)
