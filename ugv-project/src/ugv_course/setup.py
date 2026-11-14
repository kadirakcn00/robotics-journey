import os
from glob import glob

from setuptools import setup

package_name = 'ugv_course'


def tree(folder):
    """Klasoru alt klasorleriyle birlikte share/ altina kurmak icin data_files listesi."""
    out = []
    for root, _, files in os.walk(folder):
        if files:
            out.append((os.path.join('share', package_name, root),
                        [os.path.join(root, f) for f in files]))
    return out


setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'worlds'), glob('worlds/*.sdf')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
    ] + tree('models'),
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='kadir',
    maintainer_email='kadirakcn444@gmail.com',
    description='TEKNOFEST 2026 UGV course: world, water physics and sliding obstacle',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'water_physics = ugv_course.water_physics_node:main',
            'sliding_obstacle = ugv_course.sliding_obstacle_node:main',
            'course_tester = ugv_course.course_tester_node:main',
        ],
    },
)
