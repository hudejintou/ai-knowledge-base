"""天气工具：城市名 -> 经纬度（地理编码）-> 当前天气（预报）。

约定：工具永远不向外抛异常，所有失败都转成结构化错误字典返回，
由 Agent 把错误交给模型处理。
"""

import time

import requests

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

HTTP_TIMEOUT = 5          # 单次 HTTP 请求超时（秒）
MAX_RETRIES = 1           # 超时与 5xx 各最多重试 1 次
RETRY_WAIT = 1            # 重试前等待（秒）
MAX_CITY_LEN = 50

WEATHER_SCHEMA = {
    "name": "get_weather",
    "description": "查询指定城市的当前天气（温度、天气状况、风速）。城市名可用中文或英文，如 北京、Shanghai。",
    "parameters": {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "城市名，如 北京、上海、Tokyo"},
        },
        "required": ["city"],
    },
}


def _error(code, message):
    return {"error": code, "message": message}


def _get_json(url, params):
    """带一次重试的 GET。返回 (json, None) 或 (None, 错误字典)。

    只对超时和 5xx 重试；其他错误（如 4xx、连接错误、JSON 解析失败）直接返回。
    """
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, timeout=HTTP_TIMEOUT)
        except requests.Timeout:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_WAIT)
                continue
            return None, _error("timeout", "天气服务请求超时，请稍后再试")
        except requests.RequestException:
            return None, _error("internal", "网络请求失败")

        if resp.status_code >= 500:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_WAIT)
                continue
            return None, _error("upstream_unavailable", "天气服务暂时不可用")
        if resp.status_code != 200:
            return None, _error("internal", f"天气服务返回异常状态 {resp.status_code}")
        try:
            return resp.json(), None
        except ValueError:
            return None, _error("internal", "天气服务返回的数据无法解析")
    return None, _error("internal", "未知错误")


def get_weather(city):
    """查询城市当前天气。成功返回结构化结果，失败返回 {"error", "message"}。"""
    if not isinstance(city, str) or not city.strip():
        return _error("invalid_input", "城市名不能为空")
    city = city.strip()
    if len(city) > MAX_CITY_LEN:
        return _error("invalid_input", f"城市名不能超过 {MAX_CITY_LEN} 个字符")

    try:
        geo, err = _get_json(GEOCODING_URL, {"name": city, "count": 1, "language": "zh"})
        if err:
            return err
        results = geo.get("results") or []
        if not results:
            return _error("city_not_found", f"未找到城市：{city}")
        place = results[0]

        fc, err = _get_json(FORECAST_URL, {
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "current": "temperature_2m,weather_code,wind_speed_10m",
        })
        if err:
            return err
        current = fc["current"]
        return {
            "city": place.get("name", city),
            "temperature_c": current["temperature_2m"],
            "weather_code": current["weather_code"],
            "wind_kmh": current["wind_speed_10m"],
        }
    except Exception:
        # 兜底：任何未预料的解析或结构错误都不能外泄为异常
        return _error("internal", "天气查询发生内部错误")