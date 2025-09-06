A tool to parse an ansible collection.

## Setup

```
python3 -m pip install acparser
```

## Usage

```
acparser --tarfile ~/Downloads/ansible-posix-2.0.0.tar.gz
```

## Usge as a Python module

```Python
import acparser
result = acparser.process_collection("ansible", "posix", "2.0.0", "/home/adas/Downloads/ansible-posix-2.0.0.tar.gz")
```

## License

GNU General Public License v3.0 or later

## Copyright notice

Copyright (C) 2025  Anwesha Das