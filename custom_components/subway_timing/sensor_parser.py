"""Parser for subway schedule."""
import logging
import re
from datetime import datetime, timedelta

from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

class SubwayScheduleParser:
    """解析地铁时刻表配置文件."""
    
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
            schedule = {}
            
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
