"""Constants for the Subway Timing integration."""

DOMAIN = "subway_timing"
DEFAULT_NAME = "Subway Timing"
CONF_STATION = "station"
CONF_DIRECTION = "direction"
CONF_CONFIG_PATH = "config_path"
DEFAULT_CONFIG_PATH = "custom_components/subway_timing/config/info.conf"

# 属性常量
ATTR_STATION = "station"
ATTR_DIRECTION = "direction"
ATTR_NEXT_TRAINS = "next_trains"
ATTR_LAST_UPDATED = "last_updated"
ATTR_FRIENDLY_WAIT_TIME = "friendly_wait_time"
ATTR_NEXT_TRAIN_1 = "next_train_1"
ATTR_NEXT_TRAIN_2 = "next_train_2"
ATTR_NEXT_TRAIN_3 = "next_train_3"
ATTR_NEXT_TRAIN_1_TIME = "next_train_1_time"
ATTR_NEXT_TRAIN_2_TIME = "next_train_2_time"
ATTR_NEXT_TRAIN_3_TIME = "next_train_3_time"
ATTR_NEXT_TRAIN_1_WAIT = "next_train_1_wait"
ATTR_NEXT_TRAIN_2_WAIT = "next_train_2_wait"
ATTR_NEXT_TRAIN_3_WAIT = "next_train_3_wait"

# 服务常量
SERVICE_REFRESH = "refresh"
