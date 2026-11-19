from unittest.mock import MagicMock, patch

import requests
from django.test import SimpleTestCase

from agent.tools import weather


def _resp(status=200, json_data=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = json_data
    return r


GEO_OK = {"results": [{"name": "北京", "latitude": 39.9, "longitude": 116.4}]}
FC_OK = {"current": {"temperature_2m": 1.4, "weather_code": 0, "wind_speed_10m": 13.3}}


@patch("agent.tools.weather.time.sleep", return_value=None)
class GetWeatherTests(SimpleTestCase):

    @patch("agent.tools.weather.requests.get")
    def test_success(self, mock_get, _sleep):
        mock_get.side_effect = [_resp(200, GEO_OK), _resp(200, FC_OK)]
        result = weather.get_weather("北京")
        self.assertEqual(result, {"city": "北京", "temperature_c": 1.4,
                                  "weather_code": 0, "wind_kmh": 13.3})

    @patch("agent.tools.weather.requests.get")
    def test_empty_city_is_invalid_and_sends_no_request(self, mock_get, _sleep):
        self.assertEqual(weather.get_weather("  ")["error"], "invalid_input")
        mock_get.assert_not_called()

    @patch("agent.tools.weather.requests.get")
    def test_too_long_city_is_invalid(self, mock_get, _sleep):
        self.assertEqual(weather.get_weather("城" * 51)["error"], "invalid_input")
        mock_get.assert_not_called()

    @patch("agent.tools.weather.requests.get")
    def test_city_not_found(self, mock_get, _sleep):
        mock_get.return_value = _resp(200, {})  # 无 results 字段
        self.assertEqual(weather.get_weather("火星城")["error"], "city_not_found")

    @patch("agent.tools.weather.requests.get")
    def test_timeout_retries_once_then_fails(self, mock_get, sleep):
        mock_get.side_effect = requests.Timeout()
        self.assertEqual(weather.get_weather("北京")["error"], "timeout")
        self.assertEqual(mock_get.call_count, 2)  # 1 次 + 1 次重试

    @patch("agent.tools.weather.requests.get")
    def test_timeout_then_success(self, mock_get, _sleep):
        mock_get.side_effect = [requests.Timeout(), _resp(200, GEO_OK), _resp(200, FC_OK)]
        self.assertEqual(weather.get_weather("北京")["temperature_c"], 1.4)

    @patch("agent.tools.weather.requests.get")
    def test_5xx_retries_once_then_upstream_unavailable(self, mock_get, _sleep):
        mock_get.return_value = _resp(503)
        self.assertEqual(weather.get_weather("北京")["error"], "upstream_unavailable")
        self.assertEqual(mock_get.call_count, 2)

    @patch("agent.tools.weather.requests.get")
    def test_4xx_is_not_retried(self, mock_get, _sleep):
        mock_get.return_value = _resp(403)
        self.assertEqual(weather.get_weather("北京")["error"], "internal")
        self.assertEqual(mock_get.call_count, 1)

    @patch("agent.tools.weather.requests.get")
    def test_connection_error_is_not_retried(self, mock_get, _sleep):
        mock_get.side_effect = requests.ConnectionError()
        self.assertEqual(weather.get_weather("北京")["error"], "internal")
        self.assertEqual(mock_get.call_count, 1)

    @patch("agent.tools.weather.requests.get")
    def test_malformed_forecast_does_not_raise(self, mock_get, _sleep):
        mock_get.side_effect = [_resp(200, GEO_OK), _resp(200, {"unexpected": 1})]
        self.assertEqual(weather.get_weather("北京")["error"], "internal")