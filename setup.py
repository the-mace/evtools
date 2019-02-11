import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name='evtools',
    version='1.0.0',
    description='',
    url='https://github.com/the-mace/evtools',
    py_modules=['tl_tweets', 'tl_weather', 'tl_stock', 'solarcity', 'tesla', 'tl_email'],
    license='MIT',
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
