from setuptools import setup, find_packages

setup(
    name='pcap2http',
    version='1.0',
    packages=find_packages(),
    url='https://github.com/ex0dus-cpp/pcap2http',
    author='ex0dus-cpp',
    keywords='pcap http',
    description='Parse pcap file with python and watch sites in a browser or a file system',
    long_description=open('README.rst', 'r').read(),
    data_files=[('wireshark', ['pcap2http/wireshark_plugin.lua'])]
)
