from setuptools import setup
import configparser
import os


requirements = []
f = open('requirements.txt', 'r')
while True:
    l = f.readline()
    if l == '':
        break
    requirements.append(l.rstrip())
f.close()

test_requirements = []
f = open('test_requirements.txt', 'r')
while True:
    l = f.readline()
    if l == '':
        break
    test_requirements.append(l.rstrip())
f.close()

postgres_requirements = [
    'psycopg2==2.8.6',
        ] + requirements
sqlite_requirements = [
        ] + requirements
setup(
        install_requires=requirements,
        tests_require=test_requirements,
        extras_require={
            'postgres': postgres_requirements,
            'sqlite': sqlite_requirements,
            }
    )
