# Wit Init Action

This [GitHub Action](https://github.com/features/actions) will initialize a
wit workspace for a repository with a wit-manifest.json.  When used in a
complex project, an environment package should probably be specified to
describe the build environment using the additional_packages argument.

See [action.yml](./action.yml) for a detailed list of input parameters.

## Example Usage

```yaml
jobs:
  test:
    name: Scala compile
    runs-on: ubuntu-latest

    steps:
    - name: Wit Init
      uses: sifive/wit/actions/init@v0.13.2
      with:
        additional_packages: git@github.com:sifive/environment-blockci-sifive.git::0.7.0

    - name: Run wake scala compile
      uses: sifive/environment-blockci-sifive/actions/wake@0.7.0
      with:
        command: -x 'compileScalaModule myScalaModule | getPathResult'
```
