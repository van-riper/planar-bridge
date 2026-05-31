"""Pure domain logic: derives facts and decisions from MTGJSON data.

This package imports nothing from the data, network, engine, or event
layers. It takes plain dictionaries and dataclasses and returns derived
values, which is what keeps it unit-testable in isolation.
"""
