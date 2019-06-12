# wit
Workspace Integration Tool

## What's wit?
wit generates a development workspace consisting of one or more packages (generally git repositories). Each package may optionally contain a wit-manifest.json file which defines other packages upon which it depends.

wit resolves this hierarchy of dependencies and generates a flattened directory structure in which each package may exist only once.

## How Do I Use wit?
### Creating A Workspace
Creating a workspace does not require a git repository to be specified. You may create an empty workspace with:

    wit init soc
 
If you want to specify a repository when you generate the workspace you can use the -a option

    wit create soc -a /path/to/git/repo/soc.git
 
### Adding A Package To A Workspace
To add a package to a workspace that has already been created you use the add-pkg sub-command.

    wit add-pkg /path/to/git/repo/soc.git
 
### Checkout And Resolve Repository Dependencies
Once you have added one or more repositories to your workspace you can recursively read the dependency files and checkout dependent repositories.

    wit update
 
 ## License
 
See [LICENSE](./LICENSE).
