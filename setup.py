from distutils.core import setup
import setuptools
setup(
  name = 'pygazpar',         # How you named your package folder (MyLib)
  packages = ['pygazpar'],   # Chose the same as "name"
  version = '0.1.5',      # Start with a small number and increase it with every change you make
  license='MIT',        # Chose a license from here: https://help.github.com/articles/licensing-a-repository
  description = 'Retrieve gas consumption from GrDF web site (French Gas Company)',   # Give a short description about your library
  author = 'Stephane Senart',                   # Type in your name
  author_email = 'stephane.senart@gmail.com',      # Type in your E-Mail
  url = 'https://github.com/ssenart/PyGazpar',   # Provide either the link to your github or to your website
  download_url = 'https://github.com/ssenart/PyGazpar/archive/v_01.tar.gz',    # I explain this later on
  keywords = ['ENERGY', 'GAS', 'CONSUMPTION'],   # Keywords that define your package best
  install_requires=[            # I get to this in a second
          'selenium == 3.141',
          'openpyxl == 2.6.3'
      ],
  classifiers=[
    'Development Status :: 3 - Alpha',      # Chose either "3 - Alpha", "4 - Beta" or "5 - Production/Stable" as the current state of your package    'Intended Audience :: Developers',      # Define that your audience are developers
    'Topic :: Software Development :: Build Tools',    'License :: OSI Approved :: MIT License',   # Again, pick a license    'Programming Language :: Python :: 3',      #Specify which pyhton versions that you want to support
    'Programming Language :: Python :: 3.4',
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: 3.6',
    'Programming Language :: Python :: 3.7',    
  ],
)
