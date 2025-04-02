"""Config flow for Subway Timing integration."""
import os
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN, 
    DEFAULT_NAME, 
    CONF_STATION, 
    CONF_DIRECTION, 
    CONF_CONFIG_PATH,
    DEFAULT_CONFIG_PATH
)

_LOGGER = logging.getLogger(__name__)

# 直接定义SubwayScheduleParser的简化版本，避免导入问题
def parse_stations(config_file):
    """解析配置文件中的站点信息."""
    stations = {}
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            content = f.readlines()
        
        current_station = None
        current_direction = None
        
        for line in content:
            line = line.strip()
            
            # 跳过空行和注释
            if not line or line.startswith("//"):
                continue
            
            # 检查是否是站点名行
            if "方向" not in line and not line.startswith("周") and not line.startswith("小时") and not any(c.isdigit() for c in line):
                current_station = line
                if current_station not in stations:
                    stations[current_station] = []
                continue
            
            # 检查是否是方向行
            if "方向" in line and current_station and line not in stations[current_station]:
                current_direction = line
                stations[current_station].append(current_direction)
    except Exception as e:
        _LOGGER.error("解析配置文件时出错: %s", str(e))
    
    return stations

class SubwayTimingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Subway Timing."""

    VERSION = 1

    def __init__(self):
        """初始化配置流程."""
        self._stations = {}
        self._station = None
        self._config_path = DEFAULT_CONFIG_PATH

    async def async_step_user(self, user_input=None):
        """处理初始步骤."""
        errors = {}
        
        if user_input is not None:
            # 保存配置路径并继续下一步
            self._config_path = user_input.get(CONF_CONFIG_PATH, DEFAULT_CONFIG_PATH)
            
            # 检查配置文件是否存在
            # 检查配置文件是否为绝对路径
            if os.path.isabs(self._config_path):
                conf_path = self._config_path
            else:
                conf_path = os.path.join(self.hass.config.config_dir, self._config_path)
            
            if not os.path.isfile(conf_path):
                errors[CONF_CONFIG_PATH] = "file_not_found"
                _LOGGER.error("配置文件不存在: %s", conf_path)
            else:
                try:
                    # 解析配置文件获取站点信息
                    self._stations = parse_stations(conf_path)
                    
                    if not self._stations:
                        errors[CONF_CONFIG_PATH] = "no_stations_found"
                        _LOGGER.error("配置文件中未找到站点信息")
                    else:
                        return await self.async_step_station()
                except Exception as e:
                    _LOGGER.error("解析配置文件时出错: %s", str(e))
                    errors[CONF_CONFIG_PATH] = "parse_error"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_CONFIG_PATH, default=DEFAULT_CONFIG_PATH): str,
            }),
            errors=errors
        )

    async def async_step_station(self, user_input=None):
        """处理站点选择步骤."""
        errors = {}
        
        if user_input is not None:
            # 保存选定的站点，并继续到方向选择
            self._station = user_input[CONF_STATION]
            return await self.async_step_direction()
        
        # 准备站点选择选项
        stations = list(self._stations.keys())
        
        return self.async_show_form(
            step_id="station",
            data_schema=vol.Schema({
                vol.Required(CONF_STATION, default=stations[0] if stations else ""): vol.In(stations),
            }),
            errors=errors
        )
    
    async def async_step_direction(self, user_input=None):
        """处理方向选择步骤."""
        errors = {}
        
        if user_input is not None:
            direction = user_input[CONF_DIRECTION]
            
            # 创建唯一ID
            unique_id = f"{self._station}_{direction}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            
            # 创建配置条目
            return self.async_create_entry(
                title=f"{self._station} {direction}",
                data={
                    CONF_CONFIG_PATH: self._config_path,
                    CONF_STATION: self._station,
                    CONF_DIRECTION: direction,
                }
            )
        
        # 准备方向选择选项
        directions = self._stations.get(self._station, [])
        
        return self.async_show_form(
            step_id="direction",
            data_schema=vol.Schema({
                vol.Required(CONF_DIRECTION, default=directions[0] if directions else ""): vol.In(directions),
            }),
            errors=errors,
            description_placeholders={"station": self._station}
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """获取选项流程处理器."""
        return SubwayTimingOptionsFlowHandler(config_entry)


class SubwayTimingOptionsFlowHandler(config_entries.OptionsFlow):
    """处理Subway Timing的选项流程."""

    def __init__(self, config_entry):
        """初始化选项流程."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """处理选项流程."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                "update_mode",
                default=self.config_entry.options.get("update_mode", "dynamic"),
            ): vol.In({"dynamic": "动态更新", "fixed": "固定间隔"}),
            vol.Optional(
                "update_interval",
                default=self.config_entry.options.get("update_interval", 60),
            ): vol.All(vol.Coerce(int), vol.Range(min=10, max=600)),
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))
