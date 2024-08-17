# config-binder

[![downloads](https://static.pepy.tech/badge/config-binder/month)](https://pepy.tech/project/config-binder)
[![PyPI version](https://badge.fury.io/py/config-binder.svg)](https://badge.fury.io/py/config-binder)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![versions](https://img.shields.io/pypi/pyversions/config-binder.svg)](https://github.com/pydantic/pydantic)

Simple configuration parsing with recursive class binding, environment variables resolution and types safety. 


## Installation

```bash
pip install config-binder
```

## Simple example
### input.yaml
```yaml
host: ${MYAPP_HOST:localhost}
port: 5432
username: admin
password: ${MYAPP_PASSWORD}
```
### ENV exposure
```shell
export MYAPP_PASSWORD=123
```
### With binding:
```python
class MySettings:
    host: str
    port: int
    username: str
    password: str
    source_urls: List[str]


config = ConfigBinder.load('input.yaml')
print(f"type: {type(config).__name__}, config: host:{config.host} port:{config.port} source_urls:{config.source_urls}")

# Output:
# type: MySettings, config: host:localhost port:5432 source_urls:['some-url.com', 'another-url.com']
```
### Without binding
in this case data will be returned in dict with just all the environment variables resolved
```python
config = ConfigBinder.load('input.yaml')
print(f"type: {type(config).__name__}, config: {config}")

# Output:
# type: dict, config: {'host': 'localhost', 'port': 5432, 'username': 'admin', 'password': '123', 'source_urls': ['some-url.com', 'another-url.com']}
```

## More complex example
### input.yaml
```yaml
name: MyApplication
logging_level: INFO
redis_config:
  host: ${MYAPP_REDIS_HOST:127.0.0.1}
  post: ${MYAPP_REDIS_PORT:6379}
  password: ${MYAPP_REDIS_PASS}
  encryption_Key: ${MYAPP_REDIS_ENCRYPTION_KEY}
sources_configs:
  orders:
    url: some-url.com/orders
    token: ${MYAPP_ORDERS_SOURCE_TOKEN}
    retry_policy:
      max_attempts: 5
      backoff_seconds: 10
  products:
    url: another-url.com/products
    token: ${MYAPP_ORDERS_products_TOKEN}
    retry_policy:
      max_attempts: 3
      backoff_seconds: 5
```
### ENV exposure
```shell
export MYAPP_REDIS_PASS=redis_pass
export MYAPP_REDIS_ENCRYPTION_KEY=very_strong_key
export MYAPP_ORDERS_SOURCE_TOKEN=orders_token
export MYAPP_ORDERS_PRODUCTS_TOKEN=products_token
```
### Config classes definition
```python
class RedisConfig:
    host: str
    port: int
    password: str
    encryption_key: str

class RetryPolicy:
    max_attempts: int
    backoff_seconds: int

class SourceConfig:
    url: str
    token: str
    retry_policy: RetryPolicy

class AppConfig:
    name: str
    logging_level: Literal['DEBUG', 'INFO', 'ERROR']
    redis_config: RedisConfig
    sources_configs: Dict[str, SourceConfig]
```
### Binding from file
```python
config = ConfigBinder.load('input.yaml', AppConfig)
```
### Binding from `str` variable
input_yaml is variable with the same yaml specified above
```python
config = ConfigBinder.read(ConfigType.yaml, input_yaml, AppConfig)
```
### Results
input yaml is now bound to AppConfig class with env variables resolution and types validation
```python
print(config.name)
print(config.logging_level)
print(f"type: {type(config.redis_config).__name__}, config: {str(vars(config.redis_config))}")
print(f"type: {type(config.sources_configs['orders']).__name__}, config: {str(vars(config.sources_configs['orders']))}")
print(f"type: {type(config.sources_configs['products']).__name__}, config: {str(vars(config.sources_configs['products']))}")
# Output:
# MyApplication
# INFO
# type: RedisConfig, config: {'host': '127.0.0.1', 'port': 6379, 'password': 'redis_pass', 'encryption_key': 'None'}
# type: SourceConfig, config: {'url': 'some-url.com/orders', 'token': 'orders_token', 'retry_policy': <__main__.RetryPolicy object at 0x7f268fe2fe00>}
# type: SourceConfig, config: {'url': 'another-url.com/products', 'token': 'products_token', 'retry_policy': <__main__.RetryPolicy object at 0x7f268fe2fe30>}
```