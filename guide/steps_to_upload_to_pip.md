
# Steps to build 


# Steps to upload a new version of the package to pip 

details here [link] https://packaging.python.org/en/latest/tutorials/packaging-projects/

1. Configuring metadata in .\pyproject.toml

2. Update README.md
    - new version
    - any new features
    - bug fixes
    - changes in usage instructions.

4. Verify dependencies in `requirements.txt` are up-to-date.

5. Update twine 
```python
py -m pip install --upgrade twine
```

6. Delete all files in the dist folder.

7. Update the version number in the setup.py file.

8. 
``` python
py setup.py sdist bdist_wheel
```

9. Update .pypirc token [if needed]
``` cmd
cd %USERPROFILE%
dir /a 
```
Check if a file named .pypirc exists.

(if file doesnt exist create one with the text)
[distutils]
  index-servers =
    pypi
    PROJECT_NAME

[pypi]
  username = __token__
  password = # either a user-scoped token or a project-scoped token you want to set as the default
[PROJECT_NAME]
  repository = https://upload.pypi.org/legacy/
  username = __token__
  password = # a project token 


9. Update package on pip
```python
twine upload --repository pypi dist/*
``` 

