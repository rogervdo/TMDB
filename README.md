# Custom Addon - Odoo 18 Module Template

This is a blank template for creating custom Odoo 18 modules.

## Module Structure

```
custom_addon/
├── __init__.py
├── __manifest__.py
├── models/
│   └── __init__.py
├── views/
│   └── (add your view files here)
├── security/
│   └── ir.model.access.csv
├── data/
│   └── (add your data files here)
├── demo/
│   └── (add your demo files here)
├── wizard/
│   └── __init__.py
├── report/
│   └── __init__.py
├── tests/
│   └── __init__.py
├── static/
│   └── description/
│       └── icon.png
└── README.md
```

## Getting Started

1. Rename the module folder to your desired module name
2. Update the `__manifest__.py` file with your module details
3. Add your models in the `models/` directory
4. Create views in the `views/` directory
5. Update security rights in `security/ir.model.access.csv`
6. Add any data files in `data/` or `demo/` directories

## Installation

1. Copy this module to your Odoo addons directory
2. Update the addons list in Odoo
3. Install your module from the Apps menu

## License

This template is licensed under LGPL-3.

