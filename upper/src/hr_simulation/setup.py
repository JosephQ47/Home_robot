from glob import glob
from setuptools import find_packages, setup

package_name = 'hr_simulation'
setup(name=package_name, version='0.1.0', packages=find_packages(),
      data_files=[('share/ament_index/resource_index/packages', ['resource/' + package_name]),
                  ('share/' + package_name, ['package.xml']),
                  ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
                  ('share/' + package_name + '/config', glob('config/*.yaml'))],
      install_requires=['setuptools'], zip_safe=True,
      entry_points={'console_scripts': ['mock_system = hr_simulation.mock_system:main',
                                          'planar_sim = hr_simulation.planar_sim:main']})
