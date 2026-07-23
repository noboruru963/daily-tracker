from setuptools import setup, find_packages

setup(
    name='daily',
    version='1.0.0',
    description='A highly customizable habit tracker app',
    author='Daily Team',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'Flask>=2.3.3',
        'Flask-SQLAlchemy>=3.1.1',
        'Flask-Login>=0.6.2',
        'Werkzeug>=2.3.7',
        'Jinja2>=3.1.2',
        'SQLAlchemy>=2.0.23',
    ],
    extras_require={
        'dev': [
            'pytest>=7.4.0',
            'pytest-cov>=4.1.0',
        ],
    },
    python_requires='>=3.8',
)