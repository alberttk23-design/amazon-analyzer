import pytest
from backend.depth_crawler import extract_balanced_json_object, extract_balanced_json_array


def test_extract_balanced_json_object_nested():
    raw_html = '''
    <script>
    var data = {
        "dimensionValuesDisplayData" : {
            "B08ABC1234": ["Black", "Large"],
            "B08XYZ5678": ["Blue", "Medium", {"special_case": true}]
        },
        "otherKey": "hello"
    };
    </script>
    '''
    res = extract_balanced_json_object(raw_html, "dimensionValuesDisplayData")
    assert res is not None
    assert "B08ABC1234" in res
    assert res["B08ABC1234"] == ["Black", "Large"]
    assert res["B08XYZ5678"][0] == "Blue"
    assert res["B08XYZ5678"][2] == {"special_case": True}


def test_extract_balanced_json_object_with_escaped_quotes_and_braces():
    raw_script = '''
    "asinToDimensionIndexMap" = {
        "B08TEST": [0, 1],
        "B08NOTE": "String with {brace} and \\"escaped quotes\\""
    };
    '''
    res = extract_balanced_json_object(raw_script, "asinToDimensionIndexMap")
    assert res is not None
    assert res["B08TEST"] == [0, 1]
    assert "String with {brace}" in res["B08NOTE"]


def test_extract_balanced_json_array():
    raw_script = '''
    var twister = {
        "dimensionsDisplay": ["Color Name", "Size", "Style"],
        "unrelated": [1, 2, 3]
    };
    '''
    arr = extract_balanced_json_array(raw_script, "dimensionsDisplay")
    assert arr is not None
    assert arr == ["Color Name", "Size", "Style"]


def test_extract_balanced_json_not_found():
    assert extract_balanced_json_object("random text without keyword", "dimData") is None
    assert extract_balanced_json_array("random text without keyword", "dimList") is None
    assert extract_balanced_json_object("", "") is None
