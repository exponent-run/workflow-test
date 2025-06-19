We want to create a test of if we can programatically run Github actions/workflows over API. Do the following first:

- Set up this folder as a GH repo
- Push the GH repo wih the same name as the folder to the GH org https://github.com/exponent-run (the gh CLI is already authentiated to do this)
- Create a GH app called "Indent Test" that is installed into the repo
- This app should have authorization to create/run GH workflows
- Create a simple GH workflow that just echo's hi whenever it runs as one step and does a `tree` on the repo as a second step
- Write a very simple python script that, when run, executes the GH workflow, polls for it to finish, and prints the results. The GH workflow should also pull down the repo into the workflow so that the tree command can work.
- In this repo, setup the code for the GH app too

The final state should be:
- A user can install the GH app to a repo
- The GH app is used to create a workflow/action in the GH app (according to the instructions above)
- Then, whenever a specific command is run, the GH app auth is used to trigger the workflow, wait to execute, and print the result
- This app can be installed to any repo and this process can be repeated

Build this in python. Ask me for any setup steps needed, but try to iterate as much as possible before coming back to me.

 
