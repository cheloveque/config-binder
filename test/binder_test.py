from dataclasses import dataclass
from typing import Union, Optional, Literal, Tuple, List, Set, Dict

import pytest

from config_binder import ConfigBinder, ValidationError, ConfigType


def data_template(val):
    return {'field': val}


def test_load_yaml():
    class NestedConfig:
        nested_field1: int
        nested_field2: bool

    class MainConfig:
        field1: str
        field2: float
        field3: Dict[str, NestedConfig]
        field4: List[int]
        field5: Union[str, int]

    yaml_content = """
    field1: example string
    field2: 45.67
    field3:
        key1:
            nested_field1: 123
            nested_field2: true
        key2:
            nested_field1: 456
            nested_field2: false
    field4:
        - 1
        - 2
        - 3
        - 4
        - 5
    field5: some string
    """

    json_content = """
    {
    "field1": "example string",
    "field2": 45.67,
    "field3":
    {
        "key1":
        {
            "nested_field1": 123,
            "nested_field2": "True"
        },
        "key2":
        {
            "nested_field1": 456,
            "nested_field2": "False"
        }
    },
    "field4":
    [
        1,
        2,
        3,
        4,
        5
    ],
    "field5": "some string"
    }"""

    yaml_config = ConfigBinder.read(ConfigType.yaml, yaml_content, MainConfig)
    json_config = ConfigBinder.read(ConfigType.json, json_content, MainConfig)

    for config in [yaml_config, json_config]:
        assert isinstance(config, MainConfig)
        assert config.field1 == "example string"
        assert isinstance(config.field2, float)
        assert config.field2 == 45.67
        assert isinstance(config.field3, dict)
        assert 'key1' in config.field3 and isinstance(config.field3['key1'], NestedConfig)
        assert config.field3['key1'].nested_field1 == 123
        assert config.field3['key1'].nested_field2 is True
        assert 'key2' in config.field3 and isinstance(config.field3['key2'], NestedConfig)
        assert config.field3['key2'].nested_field1 == 456
        assert config.field3['key2'].nested_field2 is False
        assert isinstance(config.field4, list)
        assert config.field4 == [1, 2, 3, 4, 5]
        assert isinstance(config.field5, str)
        assert config.field5 == "some string"


def test_bind_set_list():
    class TestConfigSet:
        field: Set[int]

    test_config = ConfigBinder.bind(data_template({1, 2, 3}), TestConfigSet)
    assert isinstance(test_config.field, set) and test_config.field == {1, 2, 3}
    test_config = ConfigBinder.bind(data_template({'1', '2', '3'}), TestConfigSet)
    assert isinstance(test_config.field, set) and test_config.field == {1, 2, 3}

    with pytest.raises(ValidationError):
        ConfigBinder.bind(data_template({1, 'two', 3}), TestConfigSet)

    class TestConfigList:
        field: List[int]

    test_config = ConfigBinder.bind(data_template([1, '2', 3]), TestConfigList)
    assert isinstance(test_config.field, list) and test_config.field == [1, 2, 3]
    test_config = ConfigBinder.bind(data_template(['1', 2, '3']), TestConfigList)
    assert isinstance(test_config.field, list) and test_config.field == [1, 2, 3]

    with pytest.raises(ValidationError):
        ConfigBinder.bind(data_template(['1', 'two', '3']), TestConfigList)

    class NestedConfig:
        field: int

    class TestConfig:
        field: List[NestedConfig]

    test_config = ConfigBinder.bind(data_template([data_template(1), data_template(2), data_template(3)]), TestConfig)
    assert isinstance(test_config.field, list)
    assert all(isinstance(item, NestedConfig) for item in test_config.field)
    assert [item.field for item in test_config.field] == [1, 2, 3]

    test_config = ConfigBinder.bind(data_template([data_template('1'), data_template(2), data_template(3)]), TestConfig)
    assert isinstance(test_config.field, list)
    assert all(isinstance(item, NestedConfig) for item in test_config.field)
    assert [item.field for item in test_config.field] == [1, 2, 3]

    with pytest.raises(ValidationError):
        ConfigBinder.bind(data_template([data_template('test1'), data_template(2), data_template(3)]), TestConfig)


def test_bind_tuple():
    @dataclass
    class TestConfigNested:
        field: bool

    class TestConfigTuple:
        field: Tuple[int, str, bool, TestConfigNested]

    test_config = ConfigBinder.bind(data_template((1, 'test', True, data_template(True))), TestConfigTuple)
    assert isinstance(test_config.field, tuple) and test_config.field == (1, 'test', True, TestConfigNested(True))
    test_config = ConfigBinder.bind(data_template(('1', 'test', 'False', data_template('False'))), TestConfigTuple)
    assert isinstance(test_config.field, tuple) and test_config.field == (1, 'test', False, TestConfigNested(False))

    with pytest.raises(ValidationError):
        ConfigBinder.bind(data_template((1, 2, 3, data_template(True))), TestConfigTuple)
    with pytest.raises(ValidationError):
        ConfigBinder.bind(data_template(('False', 'False', 'False', data_template(True))), TestConfigTuple)


def test_bind_dict():
    class NestedConfig:
        nested_field: int

    class AnotherNestedConfig:
        another_field: str

    class TestConfigDictWithClasses:
        field: Dict[str, NestedConfig]
        another_field: Dict[str, AnotherNestedConfig]

    data = {'field': {'key1': {'nested_field': 123}, 'key2': {'nested_field': 456}},
            'another_field': {'keyA': {'another_field': 'valueA'}, 'keyB': {'another_field': 'valueB'}}}

    test_config = ConfigBinder.bind(data, TestConfigDictWithClasses)

    assert isinstance(test_config.field, dict)
    assert isinstance(test_config.field['key1'], NestedConfig)
    assert test_config.field['key1'].nested_field == 123
    assert isinstance(test_config.field['key2'], NestedConfig)
    assert test_config.field['key2'].nested_field == 456

    assert isinstance(test_config.another_field, dict)
    assert isinstance(test_config.another_field['keyA'], AnotherNestedConfig)
    assert test_config.another_field['keyA'].another_field == 'valueA'
    assert isinstance(test_config.another_field['keyB'], AnotherNestedConfig)
    assert test_config.another_field['keyB'].another_field == 'valueB'

    with pytest.raises(ValidationError):
        class InvalidDictKeyConfig:
            field: Dict[int, NestedConfig]

        invalid_data = {'field': {1: {'nested_field': 123}, 2: {'nested_field': 456}}}
        ConfigBinder.bind(invalid_data, InvalidDictKeyConfig)

    with pytest.raises(ValidationError):
        class InvalidDictValueConfig:
            field: Dict[str, NestedConfig]

        invalid_data = {'field': {'key1': {'nested_field': 'not an int'}, 'key2': {'nested_field': 456}}}
        ConfigBinder.bind(invalid_data, InvalidDictValueConfig)


def test_bind_literal():
    class TestConfigLiteral:
        field: Literal['option1', 'option2']

    test_config = ConfigBinder.bind(data_template('option1'), TestConfigLiteral)
    assert test_config.field == 'option1'
    test_config = ConfigBinder.bind(data_template('option2'), TestConfigLiteral)
    assert test_config.field == 'option2'

    class TestConfigLiteral:
        field: Literal[1, 2, 3, 5, 8, 13, False]

    test_config = ConfigBinder.bind(data_template(5), TestConfigLiteral)
    assert test_config.field == 5
    test_config = ConfigBinder.bind(data_template('5'), TestConfigLiteral)
    assert test_config.field == 5
    test_config = ConfigBinder.bind(data_template(13), TestConfigLiteral)
    assert test_config.field == 13
    test_config = ConfigBinder.bind(data_template('13'), TestConfigLiteral)
    assert test_config.field == 13
    test_config = ConfigBinder.bind(data_template('False'), TestConfigLiteral)
    assert test_config.field is False
    test_config = ConfigBinder.bind(data_template(False), TestConfigLiteral)
    assert test_config.field is False

    with pytest.raises(ValidationError):
        ConfigBinder.bind(data_template(33), TestConfigLiteral)
    with pytest.raises(ValidationError):
        ConfigBinder.bind(data_template('33'), TestConfigLiteral)
    with pytest.raises(ValidationError):
        ConfigBinder.bind(data_template(True), TestConfigLiteral)
    with pytest.raises(ValidationError):
        ConfigBinder.bind(data_template('True'), TestConfigLiteral)


def test_bind_union():
    class TestConfigUnion:
        field: Union[int, str, bool]

    test_config = ConfigBinder.bind(data_template(23), TestConfigUnion)
    assert isinstance(test_config.field, int) and test_config.field == 23
    test_config = ConfigBinder.bind(data_template('23'), TestConfigUnion)
    assert isinstance(test_config.field, int) and test_config.field == 23
    test_config = ConfigBinder.bind(data_template(32.2), TestConfigUnion)
    assert isinstance(test_config.field, int) and test_config.field == 32
    test_config = ConfigBinder.bind(data_template('32.2'), TestConfigUnion)
    assert isinstance(test_config.field, int) and test_config.field == 32
    test_config = ConfigBinder.bind(data_template('test'), TestConfigUnion)
    assert isinstance(test_config.field, str) and test_config.field == 'test'
    test_config = ConfigBinder.bind(data_template(True), TestConfigUnion)
    assert isinstance(test_config.field, int) and test_config.field is True
    test_config = ConfigBinder.bind(data_template('True'), TestConfigUnion)
    assert isinstance(test_config.field, int) and test_config.field is True
    test_config = ConfigBinder.bind(data_template(False), TestConfigUnion)
    assert isinstance(test_config.field, int) and test_config.field is False
    test_config = ConfigBinder.bind(data_template('False'), TestConfigUnion)
    assert isinstance(test_config.field, int) and test_config.field is False
    test_config = ConfigBinder.bind(data_template(None), TestConfigUnion)
    assert isinstance(test_config.field, str) and test_config.field == 'None'

    class TestConfigUnion:
        field: Optional[bool]  # == Union[bool, NoneType]

    test_config = ConfigBinder.bind(data_template(False), TestConfigUnion)
    assert isinstance(test_config.field, int) and test_config.field is False
    test_config = ConfigBinder.bind(data_template('False'), TestConfigUnion)
    assert isinstance(test_config.field, int) and test_config.field is False
    test_config = ConfigBinder.bind(data_template('None'), TestConfigUnion)
    assert test_config.field is None
    test_config = ConfigBinder.bind(data_template(None), TestConfigUnion)
    assert test_config.field is None

    with pytest.raises(ValidationError):
        ConfigBinder.bind(data_template(23), TestConfigUnion)
    with pytest.raises(ValidationError):
        ConfigBinder.bind(data_template('23'), TestConfigUnion)
    with pytest.raises(ValidationError):
        ConfigBinder.bind(data_template('test'), TestConfigUnion)


def test_bind_int():
    class TestConfigInt:
        field: int

    test_config = ConfigBinder.bind(data_template('23'), TestConfigInt)
    assert isinstance(test_config.field, int) and test_config.field == 23
    test_config = ConfigBinder.bind(data_template(23), TestConfigInt)
    assert isinstance(test_config.field, int) and test_config.field == 23
    test_config = ConfigBinder.bind(data_template('7.12'), TestConfigInt)
    assert isinstance(test_config.field, int) and test_config.field == 7
    test_config = ConfigBinder.bind(data_template(7.12), TestConfigInt)
    assert isinstance(test_config.field, int) and test_config.field == 7
    test_config = ConfigBinder.bind(data_template('-23'), TestConfigInt)
    assert isinstance(test_config.field, int) and test_config.field == -23
    test_config = ConfigBinder.bind(data_template('000000'), TestConfigInt)
    assert isinstance(test_config.field, int) and test_config.field == 0
    test_config = ConfigBinder.bind(data_template('00000023'), TestConfigInt)
    assert isinstance(test_config.field, int) and test_config.field == 23

    with pytest.raises(ValidationError):
        ConfigBinder.bind(data_template(True), TestConfigInt)
    with pytest.raises(ValidationError):
        ConfigBinder.bind(data_template('True'), TestConfigInt)
    with pytest.raises(ValidationError):
        ConfigBinder.bind(data_template(None), TestConfigInt)


def test_bind_float():
    class TestConfigFloat:
        field: float

    test_config = ConfigBinder.bind(data_template('32.2'), TestConfigFloat)
    assert isinstance(test_config.field, float) and test_config.field == 32.2
    test_config = ConfigBinder.bind(data_template(32.2), TestConfigFloat)
    assert isinstance(test_config.field, float) and test_config.field == 32.2
    test_config = ConfigBinder.bind(data_template('7'), TestConfigFloat)
    assert isinstance(test_config.field, float) and test_config.field == 7
    test_config = ConfigBinder.bind(data_template(7), TestConfigFloat)
    assert isinstance(test_config.field, float) and test_config.field == 7
    test_config = ConfigBinder.bind(data_template('-23'), TestConfigFloat)
    assert isinstance(test_config.field, float) and test_config.field == -23
    test_config = ConfigBinder.bind(data_template('000000'), TestConfigFloat)
    assert isinstance(test_config.field, float) and test_config.field == 0
    test_config = ConfigBinder.bind(data_template('00000032.2'), TestConfigFloat)
    assert isinstance(test_config.field, float) and test_config.field == 32.2

    with pytest.raises(ValidationError):
        ConfigBinder.bind(data_template('True'), TestConfigFloat)
    with pytest.raises(ValidationError):
        ConfigBinder.bind(data_template(None), TestConfigFloat)


def test_bind_bool():
    class TestConfigBool:
        field: bool

    test_config = ConfigBinder.bind(data_template('True'), TestConfigBool)
    assert isinstance(test_config.field, bool) and test_config.field is True
    test_config = ConfigBinder.bind(data_template('False'), TestConfigBool)
    assert isinstance(test_config.field, bool) and test_config.field is False
    test_config = ConfigBinder.bind(data_template(True), TestConfigBool)
    assert isinstance(test_config.field, bool) and test_config.field is True
    test_config = ConfigBinder.bind(data_template(False), TestConfigBool)
    assert isinstance(test_config.field, bool) and test_config.field is False

    with pytest.raises(ValidationError):
        ConfigBinder.bind(data_template('1'), TestConfigBool)
    with pytest.raises(ValidationError):
        ConfigBinder.bind(data_template('0'), TestConfigBool)
    with pytest.raises(ValidationError):
        ConfigBinder.bind(data_template(1), TestConfigBool)
    with pytest.raises(ValidationError):
        ConfigBinder.bind(data_template(0), TestConfigBool)
    with pytest.raises(ValidationError):
        ConfigBinder.bind(data_template('test'), TestConfigBool)
    with pytest.raises(ValidationError):
        ConfigBinder.bind(data_template(1412), TestConfigBool)
    with pytest.raises(ValidationError):
        ConfigBinder.bind(data_template(0.1), TestConfigBool)
    with pytest.raises(ValidationError):
        ConfigBinder.bind(data_template(None), TestConfigBool)


def test_bind_str():
    class TestConfigStr:
        field: str

    test_config = ConfigBinder.bind(data_template('test'), TestConfigStr)
    assert isinstance(test_config.field, str) and test_config.field == 'test'
    test_config = ConfigBinder.bind(data_template('23'), TestConfigStr)
    assert isinstance(test_config.field, str) and test_config.field == '23'
    test_config = ConfigBinder.bind(data_template(23), TestConfigStr)
    assert isinstance(test_config.field, str) and test_config.field == '23'
    test_config = ConfigBinder.bind(data_template('32.2'), TestConfigStr)
    assert isinstance(test_config.field, str) and test_config.field == '32.2'
    test_config = ConfigBinder.bind(data_template(32.2), TestConfigStr)
    assert isinstance(test_config.field, str) and test_config.field == '32.2'
    test_config = ConfigBinder.bind(data_template(False), TestConfigStr)
    assert isinstance(test_config.field, str) and test_config.field == 'False'
    test_config = ConfigBinder.bind(data_template(None), TestConfigStr)
    assert isinstance(test_config.field, str) and test_config.field == 'None'
