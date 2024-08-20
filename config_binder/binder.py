import ast
import os
import re
from enum import Enum
from pathlib import Path
from types import NoneType
from typing import Type, get_type_hints, Dict, Any, TypeVar, Literal, Union, Tuple, List, Set, Self

import yaml
import json
from yaml import SafeLoader, ScalarNode

ENV_VARIABLE_REGEX = re.compile(r'.*?\$\{([^{:}]+)(:?)([^}]+)?}.*?')
FILE_ENCODING = 'utf-8'

ERROR_MSG = 'Failed to load a configuration'

primitive_types = [bool, int, float, NoneType, str]


class ValidationError(Exception):
    pass


class ConfigType(Enum):
    yaml = ['.yaml', '.yml']
    json = ['.json']

    @classmethod
    def of_extension(cls, extension: str) -> Self:
        for config_type in cls:
            if extension in config_type.value:
                return config_type
        raise ValueError(f'Unsupported type extension: {extension}, supported types: {[ct.value for ct in cls]}')


# noinspection PyUnresolvedReferences
class ConfigBinder:
    T = TypeVar('T')

    @classmethod
    def load(cls, path: str, class_to_bind: Type[T] = None) -> Dict | T:
        if not path:
            raise ValueError(f'{ERROR_MSG}, path is not specified')
        path = Path(path)
        with open(path, encoding=FILE_ENCODING) as data:
            return cls.read(ConfigType.of_extension(path.suffix), data.read(), class_to_bind)

    @classmethod
    def read(cls, config_type: ConfigType, data, class_to_bind: Type[T] = None) -> Dict | T:
        if not data:
            raise ValueError(f'{ERROR_MSG}, data is empty')

        try:
            match config_type:
                case ConfigType.yaml:
                    parsed = cls.__parse_yaml(data)
                case ConfigType.json:
                    parsed = cls.__parse_json(data)
                case _:
                    raise ValueError(f"Unsupported ConfigType: {config_type}")
        except Exception as ex:
            raise ValueError(f'{ERROR_MSG}, parsing error occurred: {str(ex)}')

        if not class_to_bind:
            return parsed

        return cls.bind(parsed, class_to_bind)

    @classmethod
    def bind(cls, data: Any, clazz: Type[T]) -> T:
        if clazz in primitive_types:
            return cls.__bind_simple_type(data, clazz)
        else:
            return cls.__bind_class(data, clazz)

    @classmethod
    def __parse_yaml(cls, data: str) -> dict:
        loader = cls.__create_loader()
        return yaml.load(data, Loader=loader)

    @classmethod
    def __parse_json(cls, data: str) -> dict:
        return json.loads(data)

    @classmethod
    def __create_loader(cls) -> Type[SafeLoader]:
        loader = yaml.SafeLoader
        loader.add_implicit_resolver(None, ENV_VARIABLE_REGEX, None)
        # noinspection PyTypeChecker
        loader.add_constructor(None, cls.__constructor)
        return loader

    @classmethod
    def __constructor(cls, loader: SafeLoader, node: ScalarNode):
        to_resolve = loader.construct_scalar(node)
        for variable, separator, default_value in ENV_VARIABLE_REGEX.findall(to_resolve):
            value = os.environ.get(variable, default_value)
            if not value and ':' not in to_resolve:
                raise ValueError(f'unable to resolve placeholder {variable}')
            to_resolve = to_resolve.replace(f'${{{variable}{separator}{default_value}}}', value)
        return to_resolve

    @classmethod
    def __bind_class(cls, data: dict, clazz: Type[T]) -> T:
        type_hints = get_type_hints(clazz)
        kw_fields = {}

        for field_name, field_type in type_hints.items():
            try:
                field_data = data.get(field_name)
                if cls.__if_custom_class(field_type):
                    kw_fields[field_name] = cls.__bind_class(field_data, field_type)
                elif cls.__if_collection(field_type):
                    if field_type.__origin__ in [list, set]:
                        kw_fields[field_name] = cls.__bind_set_list(field_data, field_type)
                    elif field_type.__origin__ is tuple:
                        kw_fields[field_name] = cls.__bind_tuple(field_data, field_type)
                    elif field_type.__origin__ is dict:
                        kw_fields[field_name] = cls.__bind_dict(field_data, field_type)
                elif cls.__if_literal(field_type):
                    kw_fields[field_name] = cls.__bind_literal(field_data, field_type)
                elif cls.__if_union(field_type):
                    kw_fields[field_name] = cls.__bind_union(field_data, field_type)
                else:
                    kw_fields[field_name] = cls.__bind_simple_type(field_data, field_type)
            except Exception as ex:
                raise ValidationError(f"Failed to bind \'{field_name}\' field: {ex.__str__()}")

        try:
            bind = clazz(**kw_fields)
        except (TypeError, ValueError):
            bind = clazz.__new__(clazz)
            for field, value in kw_fields.items():
                setattr(bind, field, value)
        return bind

    @staticmethod
    def __if_custom_class(clazz: Type[Any]):
        return hasattr(clazz, '__annotations__') and not issubclass(clazz, Enum) and clazz is not Any

    @staticmethod
    def __if_collection(clazz: Type[Any]):
        return hasattr(clazz, '__origin__') and clazz.__origin__ in [list, set, dict, tuple]

    @staticmethod
    def __if_literal(clazz: Type[Any]):
        return hasattr(clazz, '__origin__') and clazz.__origin__ is Literal

    @staticmethod
    def __if_union(clazz: Type[Any]):
        return hasattr(clazz, '__origin__') and clazz.__origin__ is Union

    @classmethod
    def __bind_set_list(cls, field_data: [Set | List], field_type: Type[Any]) -> [Set | List]:
        item_type = field_type.__args__[0]
        return field_type.__origin__([cls.bind(item, item_type) for item in field_data])

    @classmethod
    def __bind_tuple(cls, field_data: Tuple, field_type: Type[Any]) -> Tuple:
        return tuple(cls.bind(item, item_type) for item, item_type in zip(field_data, field_type.__args__))

    @classmethod
    def __bind_dict(cls, field_data: Dict, field_type: Type[Any]) -> Dict:
        key_type, value_type = field_type.__args__[0], field_type.__args__[1]
        if key_type is not str:
            raise ValidationError(f"Only str keys dicts supported; found Dict keys with type \'{key_type.__name__}\'")
        if cls.__if_custom_class(value_type):
            return {key: cls.__bind_class(value, value_type) for key, value in field_data.items()}
        else:
            return field_data

    @classmethod
    def __bind_literal(cls, field_data: str, field_type: Type[Any]) -> Any:
        for possible_arg in field_type.__args__:
            try:
                bind = cls.__bind_simple_type(field_data, type(possible_arg))
                if bind == possible_arg:
                    return bind
            except Exception:
                pass
        raise ValidationError(f"Cannot bind \'{field_data}\' to Literal{field_type.__args__}")

    @classmethod
    def __bind_union(cls, field_data: Union, field_type: Type[Any]) -> Any:
        field_types = field_type.__args__
        for field_type in [ft for ft in field_types if ft not in primitive_types]:
            try:
                return cls.__bind_class(field_data, field_type)
            except Exception:
                pass

        primitive_fields_types = [ft for ft in field_types if ft in primitive_types]
        primitive_fields_types = sorted(primitive_fields_types, key=lambda t: primitive_types.index(t))

        for primitive_field_type in primitive_fields_types:
            try:
                return cls.__bind_simple_type(field_data, primitive_field_type)
            except Exception:
                pass

        if str in field_types:
            return field_data
        raise ValidationError(f"Cannot bind \'{field_data}\' to Union{field_types}")

    @classmethod
    def __bind_simple_type(cls, field_data: Any, field_type: Type[Any]) -> Any:
        try:
            if type(field_data) is field_type:
                return field_data
            if isinstance(field_data, bool):
                field_data = str(field_data)

            if field_type is int:
                return int(float(field_data))
            if field_type is bool:
                if isinstance(field_data, str):
                    match field_data.lower():
                        case 'true':
                            return True
                        case 'false':
                            return False
                raise ValueError()
            if field_type is NoneType:
                if ast.literal_eval(str(field_data)) is None:
                    return None
            return field_type(field_data)
        except (TypeError, ValueError):
            raise ValidationError(f"Cannot bind value \'{field_data}\' to type \'{field_type.__name__}\'")
