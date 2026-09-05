"""Tests for region classification."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from utils import classify_region, extract_province, extract_isp


class TestClassifyRegion:
    def test_huadong(self):
        assert classify_region("上海电信") == "华东"
        assert classify_region("江苏南京联通") == "华东"
        assert classify_region("浙江杭州移动") == "华东"
        assert classify_region("安徽合肥电信") == "华东"
        assert classify_region("福建厦门联通") == "华东"
        assert classify_region("江西南昌移动") == "华东"
        assert classify_region("山东济南电信") == "华东"

    def test_huabei(self):
        assert classify_region("北京电信") == "华北"
        assert classify_region("天津联通") == "华北"
        assert classify_region("河北石家庄移动") == "华北"
        assert classify_region("山西太原电信") == "华北"
        assert classify_region("内蒙古呼和浩特联通") == "华北"

    def test_huazhong(self):
        assert classify_region("湖北武汉电信") == "华中"
        assert classify_region("湖南长沙联通") == "华中"
        assert classify_region("河南郑州移动") == "华中"

    def test_huanan(self):
        assert classify_region("广东广州电信") == "华南"
        assert classify_region("广西南宁联通") == "华南"
        assert classify_region("海南海口移动") == "华南"

    def test_xinan(self):
        assert classify_region("四川成都电信") == "西南"
        assert classify_region("重庆联通") == "西南"
        assert classify_region("贵州贵阳移动") == "西南"
        assert classify_region("云南昆明电信") == "西南"
        assert classify_region("西藏拉萨联通") == "西南"

    def test_xibei(self):
        assert classify_region("陕西西安电信") == "西北"
        assert classify_region("甘肃兰州联通") == "西北"
        assert classify_region("青海西宁移动") == "西北"
        assert classify_region("宁夏银川电信") == "西北"
        assert classify_region("新疆乌鲁木齐联通") == "西北"

    def test_dongbei(self):
        assert classify_region("辽宁沈阳电信") == "东北"
        assert classify_region("吉林长春联通") == "东北"
        assert classify_region("黑龙江哈尔滨移动") == "东北"

    def test_gangaotai(self):
        assert classify_region("香港电信") == "港澳台"
        assert classify_region("澳门联通") == "港澳台"
        assert classify_region("台湾台北移动") == "港澳台"

    def test_overseas(self):
        assert classify_region("日本东京") == "海外"
        assert classify_region("美国圣何塞") == "海外"
        assert classify_region("新加坡") == "海外"
        assert classify_region("德国法兰克福") == "海外"
        assert classify_region("韩国首尔") == "海外"

    def test_unknown(self):
        assert classify_region("未知地点") == "未知"
        assert classify_region("") == "未知"


class TestExtractProvince:
    def test_basic(self):
        assert extract_province("上海电信") == "上海"
        assert extract_province("北京联通") == "北京"
        assert extract_province("广东广州移动") == "广东"
        assert extract_province("四川成都电信") == "四川"

    def test_no_match(self):
        assert extract_province("东京") == ""
        assert extract_province("") == ""


class TestExtractISP:
    def test_basic(self):
        assert extract_isp("上海电信") == "电信"
        assert extract_isp("北京联通") == "联通"
        assert extract_isp("广东广州移动") == "移动"

    def test_no_match(self):
        assert extract_isp("东京") == ""
        assert extract_isp("") == ""
