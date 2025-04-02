"""Subway Timing Sensor for Home Assistant."""
import os
import logging
import re
from datetime import datetime, time, timedelta

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import dt as dt_util
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_point_in_utc_time

from .const import (
    DOMAIN, 
    DEFAULT_NAME, 
    CONF_STATION, 
    CONF_DIRECTION, 
    CONF_CONFIG_PATH,
    DEFAULT_CONFIG_PATH,
)
from .sensor_parser import SubwayScheduleParser

_LOGGER = logging.getLogger(__name__)

# 保留YAML配置支持
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_CONFIG_PATH, default=DEFAULT_CONFIG_PATH): cv.string,
        vol.Optional(CONF_STATION): cv.string,
        vol.Optional(CONF_DIRECTION): cv.string,
    }
)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """通过YAML配置设置Subway Timing传感器."""
    name = config.get(CONF_NAME)
    config_path = config.get(CONF_CONFIG_PATH)
    station = config.get(CONF_STATION)
    direction = config.get(CONF_DIRECTION)
    
    # 读取配置文件路径
    # 检查配置文件是否为绝对路径
    if os.path.isabs(config_path):
        conf_path = config_path
    else:
        conf_path = os.path.join(hass.config.config_dir, config_path)
    
    if not os.path.isfile(conf_path):
        _LOGGER.error("配置文件 %s 不存在，请检查路径并确保文件已创建", conf_path)
        return
    
    # 解析配置文件
    schedule_parser = SubwayScheduleParser(conf_path)
    stations = schedule_parser.get_stations()
    
    if not stations:
        _LOGGER.error("配置文件中未找到站点信息，请检查文件格式是否正确")
        return
    
    # 创建协调器
    coordinator = SubwayTimingUpdateCoordinator(hass, schedule_parser)
    await coordinator.async_refresh()
    
    entities = []
    
    # 如果指定了站点和方向，只添加指定的传感器
    if station and direction:
        if station in stations and direction in stations[station]:
            unique_id = f"subway_timing_{station}_{direction}"
            entities.append(SubwayTimingSensor(
                coordinator, f"{name} {station} {direction}",
                station, direction, unique_id=unique_id))
        else:
            _LOGGER.error("找不到指定的站点或方向：%s %s", station, direction)
    else:
        # 添加配置文件中所有站点和方向的传感器
        for station_name, directions in stations.items():
            for direction_name in directions:
                unique_id = f"subway_timing_{station_name}_{direction_name}"
                entities.append(SubwayTimingSensor(
                    coordinator, f"{name} {station_name} {direction_name}",
                    station_name, direction_name, unique_id=unique_id))
    
    async_add_entities(entities, True)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """通过配置条目设置地铁时刻表传感器."""
    config = config_entry.data
    config_path = config.get(CONF_CONFIG_PATH, DEFAULT_CONFIG_PATH)
    station = config.get(CONF_STATION)
    direction = config.get(CONF_DIRECTION)
    
    _LOGGER.debug("设置实体: 站点=%s, 方向=%s", station, direction)
    
    # 读取配置文件路径
    # 检查配置文件是否为绝对路径
    if os.path.isabs(config_path):
        conf_path = config_path
    else:
        conf_path = os.path.join(hass.config.config_dir, config_path)
    
    if not os.path.isfile(conf_path):
        _LOGGER.error("配置文件 %s 不存在", conf_path)
        return
    
    # 解析配置文件并创建传感器
    schedule_parser = SubwayScheduleParser(conf_path)
    
    if station and direction:
        entity = SubwayTimingSensor(
            schedule_parser, station, direction, 
            config_entry.unique_id, config_entry.entry_id)
        _LOGGER.debug("添加实体: %s", entity.name)
        async_add_entities([entity], True)

class SubwayScheduleParser:
    """解析地铁时刻表配置文件."""
    # ... existing code ...
    
    def __init__(self, config_file):
        """初始化解析器."""
        self.config_file = config_file
        self.stations = {}
        self._parse_schedule()
    
    def _parse_schedule(self):
        """解析时刻表文件."""
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                content = f.readlines()
            
            current_station = None
            current_direction = None
            current_days = None
            current_hour = None
            
            for line in content:
                line = line.strip()
                
                # 跳过空行和注释
                if not line or line.startswith("//"):
                    continue
                
                # 检查是否是站点名行
                if not line.startswith("小时 |") and not re.match(r'^\d+(\s+\d+)*$', line) and "方向" not in line and not line.startswith("周"):
                    current_station = line
                    if current_station not in self.stations:
                        self.stations[current_station] = {}
                    continue
                
                # 检查是否是方向行
                if "方向" in line:
                    current_direction = line
                    if current_direction not in self.stations[current_station]:
                        self.stations[current_station][current_direction] = {}
                    continue
                
                # 检查是否是星期行
                if line.startswith("周"):
                    current_days = line
                    if current_days not in self.stations[current_station][current_direction]:
                        self.stations[current_station][current_direction][current_days] = {}
                    continue
                
                # 检查是否是表头行
                if line.startswith("小时 |"):
                    continue
                
                # 处理时间行
                if re.match(r'^\d+(\s+\d+)*$', line):
                    parts = line.split()
                    
                    if len(parts) >= 1:
                        current_hour = int(parts[0])
                        
                        if current_hour not in self.stations[current_station][current_direction][current_days]:
                            self.stations[current_station][current_direction][current_days][current_hour] = []
                        
                        # 如果有分钟数据
                        if len(parts) > 1:
                            for minute in parts[1:]:
                                try:
                                    minute_val = int(minute)
                                    if 0 <= minute_val < 60:
                                        self.stations[current_station][current_direction][current_days][current_hour].append(minute_val)
                                except ValueError:
                                    pass
        
        except Exception as e:
            _LOGGER.error("解析配置文件时出错：%s", str(e))
    
    def get_stations(self):
        """获取所有站点信息."""
        return self.stations
    
    def get_next_times(self, station, direction, current_time=None):
        """获取接下来的三趟地铁时间."""
        if current_time is None:
            current_time = dt_util.now()
        
        # 确定今天是周几
        weekday = current_time.weekday()  # 0-6，0是周一
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        current_weekday = weekday_names[weekday]
        
        if station not in self.stations:
            return []
        
        if direction not in self.stations[station]:
            return []
        
        # 查找包含当前星期几的时刻表
        days_key = None
        for key in self.stations[station][direction]:
            if key.startswith("周") and current_weekday in key:
                days_key = key
                break
        
        # 如果没找到匹配的时刻表，返回空列表
        if days_key is None:
            _LOGGER.warning("未找到站点 %s %s 星期 %s 的时刻表", station, direction, current_weekday)
            return []
        
        schedule = self.stations[station][direction][days_key]
        
        current_hour = current_time.hour
        current_minute = current_time.minute
        
        next_times = []
        
        # 查找当前小时及后续小时的班次
        hours_to_check = list(range(current_hour, 24)) + list(range(0, current_hour))
        
        for hour in hours_to_check:
            if hour in schedule:
                for minute in sorted(schedule[hour]):
                    # 如果是当前小时，只检查未来的分钟
                    if hour == current_hour and minute <= current_minute:
                        continue
                    
                    # 创建下一班车时间
                    next_train_time = current_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    
                    # 如果是明天的班次
                    if hour < current_hour:
                        next_train_time = next_train_time + timedelta(days=1)
                    
                    next_times.append(next_train_time)
                    
                    # 只取三趟车
                    if len(next_times) >= 3:
                        return next_times
        
        return next_times

class SubwayTimingSensor(SensorEntity):
    """地铁到站时间传感器."""
    
    def __init__(self, schedule_parser, station, direction, unique_id=None, entry_id=None):
        """初始化传感器."""
        self._schedule_parser = schedule_parser
        self._station = station
        self._direction = direction
        self._state = None
        self._attrs = {}
        self._entry_id = entry_id
        self._next_update_time = None
        self._unsub_update = None
        
        # 确保实体唯一ID正确设置
        self._attr_unique_id = unique_id or f"subway_timing_{station}_{direction}".lower().replace(" ", "_")
        
        # 修改实体名称配置，使用翻译键
        self._attr_has_entity_name = True
        self._attr_translation_key = "subway_timing"
        # 设置设备类为站点名称
        self._attr_device_class = f"{station}"
        # 设置实体名称为方向名称
        self._attr_name = direction
        self._attr_icon = "mdi:subway"
        
        _LOGGER.debug("创建传感器: %s, unique_id: %s", self._attr_name, self._attr_unique_id)
    
    async def async_added_to_hass(self):
        """当实体添加到 Home Assistant 时调用."""
        await self._update_and_schedule_next()
    
    async def async_will_remove_from_hass(self):
        """当实体从 Home Assistant 中移除时调用."""
        self._remove_scheduled_update()
    
    @callback
    def _remove_scheduled_update(self):
        """移除计划的更新."""
        if self._unsub_update is not None:
            self._unsub_update()
            self._unsub_update = None
    
    async def _update_and_schedule_next(self, *_):
        """更新状态并安排下一次更新."""
        self._remove_scheduled_update()
        
        # 更新状态
        await self.async_update()
        self.async_write_ha_state()
        
        # 安排下一次更新
        next_update_in = self._calculate_update_interval()
        next_update = dt_util.utcnow() + timedelta(seconds=next_update_in)
        
        _LOGGER.debug(
            "%s: 安排下一次更新在 %s 秒后 (%s)",
            self.name,
            next_update_in,
            next_update
        )
        
        self._unsub_update = async_track_point_in_utc_time(
            self.hass, self._update_and_schedule_next, next_update
        )
    
    def _calculate_update_interval(self):
        """计算下一次更新时间间隔."""
        next_times = self._schedule_parser.get_next_times(
            self._station, self._direction)
        
        if not next_times:
            # 如果没有班次，每10分钟检查一次
            return 600
        
        # 计算下一班列车的等待时间（秒）
        wait_seconds = (next_times[0] - dt_util.now()).total_seconds()
        
        # 根据等待时间调整更新频率
        if wait_seconds < 60:  # 少于1分钟
            return 10  # 每10秒更新一次
        elif wait_seconds < 300:  # 少于5分钟
            return 30  # 每30秒更新一次
        elif wait_seconds < 900:  # 少于15分钟
            return 60  # 每1分钟更新一次
        elif wait_seconds < 1800:  # 少于30分钟
            return 120  # 每2分钟更新一次
        else:
            return 300  # 每5分钟更新一次
    
    async def async_update(self):
        """更新状态."""
        next_times = self._schedule_parser.get_next_times(
            self._station, self._direction)
        
        if not next_times:
            self._state = "无班次"
            # 使用规范化的属性名称方便翻译
            self._attrs = {
                "station": self._station,
                "direction": self._direction,
                "friendly_wait_time": "暂无班次",
                "next_trains": [],
                "last_updated": dt_util.now().isoformat(),
            }
            return
        
        # 计算下一班列车的等待时间
        now = dt_util.now()
        next_train = next_times[0]
        wait_time = (next_train - now).total_seconds() // 60
        
        self._state = int(wait_time)
        
        # 创建友好的等待时间字符串
        if wait_time < 1:
            friendly_wait = "即将到站"
        elif wait_time == 1:
            friendly_wait = "1分钟后到站"
        else:
            friendly_wait = f"{int(wait_time)}分钟后到站"
        
        # 准备额外属性
        next_trains_info = []
        for idx, train_time in enumerate(next_times):
            wait_mins = (train_time - now).total_seconds() // 60
            next_trains_info.append({
                "departure_time": train_time.strftime("%H:%M"),
                "wait_time": f"{int(wait_mins)} 分钟"
            })
        
        # 基础属性 - 使用规范名称
        self._attrs = {
            "station": self._station,
            "direction": self._direction,
            "friendly_wait_time": friendly_wait,
            "next_train": next_trains_info[0] if next_trains_info else None,
            "next_trains": next_trains_info,
            "last_updated": now.isoformat(),
        }
        
        # 添加独立的未来三趟列车属性
        for i, train_info in enumerate(next_trains_info[:3], 1):
            self._attrs[f"next_train_{i}"] = train_info
            self._attrs[f"next_train_{i}_time"] = train_info["departure_time"]
            self._attrs[f"next_train_{i}_wait"] = train_info["wait_time"]
    
    @property
    def state(self):
        """返回传感器状态."""
        return self._state
    
    @property
    def extra_state_attributes(self):
        """返回额外属性."""
        return self._attrs
    
    @property
    def device_info(self):
        """返回设备信息."""
        return {
            "identifiers": {(DOMAIN, f"{self._station}_{self._direction}")},
            "name": f"地铁 {self._station}",
            "manufacturer": "Subway Timing",
            "model": self._direction,
        }
