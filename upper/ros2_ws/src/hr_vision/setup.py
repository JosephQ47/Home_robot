from setuptools import setup

setup(
    name='hr_vision', version='0.1.0', packages=['hr_vision'],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/hr_vision']),
        ('share/hr_vision', ['package.xml']),
        ('share/hr_vision/launch', ['launch/vision.launch.py']),
    ],
    install_requires=['setuptools'],
    tests_require=['pytest'],
    entry_points={'console_scripts': [
        'image_source = hr_vision.source:main',
        'perception = hr_vision.perception:main',
    ]},
)
