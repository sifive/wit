# Wit GitHub Action

This [GitHub Action](https://github.com/features/actions) will run any arbitrary
Wit command. Since it is packaged as a Docker-based command, it has all of its
dependencies included and can be used to initialize and run commands on any Wit
workspace.

See [action.yml](./action.yml) for a detailed list of input parameters.

## Example Usage

```yaml
- name: 'Wit Init'
  uses: sifive/wit/actions/wit@v0.11.2
  with:
    command: init
    arguments: |
      workspace_dir
      -a ./path/to/local/git/repo/api-scala-sifive
      -a git@github.com:sifive/environment-blockci-sifive.git::0.3.0
    force_github_https: true
```
