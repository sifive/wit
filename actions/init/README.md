# Wit Init Action

This [GitHub Action](https://github.com/features/actions) will initialize a
wit workspace for a repository with a wit-manifest.json. An environment
package should be specified to describe the build environment. By default,
environment-example-sifive is used to support reading a JSON description.

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
        environment: git@github.com:sifive/environment-blockci-sifive.git::0.7.0

    - name: Run wake scala compile
      uses: sifive/environment-blockci-sifive/actions/wake@0.7.0
      with:
        command: -x 'compileScalaModule myScalaModule | getPathResult'
```
