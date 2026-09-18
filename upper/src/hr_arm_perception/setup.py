from glob import glob
from setuptools import find_packages, setup

package_name = 'hr_arm_perception'
setup(name=package_name, version='0.1.0', packages=find_packages(exclude=['test']),
      data_files=[('share/ament_index/resource_index/packages', ['resource/' + package_name]),
                  ('share/' + package_name, ['package.xml']),
                  ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
                  ('share/' + package_name + '/config', glob('config/*.yaml')),
                  ('share/' + package_name + '/calibration', glob('calibration/*.json'))],
      install_requires=['setuptools'], zip_safe=True,
      entry_points={'console_scripts': ['arm_perception = hr_arm_perception.node:main']})
