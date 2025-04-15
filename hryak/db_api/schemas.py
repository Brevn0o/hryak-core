_schemas = {}

def set_schema(name, value):
    _schemas[name] = value

def get_schema(name):
    if name not in _schemas:
        raise Exception(f"Schema '{name}' not set.")
    return _schemas[name]