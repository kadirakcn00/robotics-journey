from setuptools import setup

package_name = 'ugv_autonomy'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='kadir',
    maintainer_email='kadirakcn444@gmail.com',
    description='Autonomous run of the TEKNOFEST course: localization, cones, slider, shooting',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'mission = ugv_autonomy.mission_node:main',
        ],
    },
)
