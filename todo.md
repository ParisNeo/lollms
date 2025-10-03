new ui:

- OK - add edit button to bubbles
- OK- fix personalities
- OK - implement MCPS
- OK - add <think> block handling
- OK when generating, remove the input and show an animation instead
- OK in chatinput, when we press shift+enter replace the input with a code mirror with a toolbar
- OK generating title add spinner 
- OK fix delete message
- OK add information about left hops
- OK level : 0 to 5
- OK social activate/deactivate
- OK fix rag store building
- OK refresh discussion after generation
- OK add authenticate with email
- OK setup default page (new discussion/social networks)
- OK revamp RAG datastores interface to put it in its own view
- OK After stopping, save current status and refresh discussion
- OK auto title
- OK the steps must by default be closed
- OK the steps content must not exceed some length in the title mode
- OK use the name of the personality in bubble instead of assistant also add its icon if applicable
- OK override the copy button
- OK make sure the images stay after generation
- OK add a reload mcps to the admin page
- OK change the interface to use a left bar and move the return to interface to the bottom of that bar
- OK the modal looses information when another modal is shown
- OK user management page needs upgrade and bugfix
- OK make it possible to load any image file for mcp icons and set reduce their size automatically
- OK key generation for regular users
- OK centralize background processes
- OK add email sending to tasks
- OK add applications/mcps log in with permissions via introspect
- OK add a forgot my password button to the login modal that sends a notification to the administrator.
- OK add the apps zoo to lollms_chat
- OK fix forced context size to actually force the context size when i choose another aliased model with forcing activated
- OK fix multi workers apps orphans detection to use a singleton
- OK task status is not automatically updated and reflected on all the ui
- OK when a task is done, it needs to update the corresponding ui
- OK Add discussion groups
- OK Left sidebar must be collapsible
- OK pressing a discussion must switch to discussion view instead of feed
- OK fix installation process
- OK start/stop events must be collapsible, all that happens in between should be put inside in between
- OK support for equations with /[ /] format
- OK fix branching
- OK the remove is not updating the discussion after removing
- OK share discussion with friends with permission to participate to the discussion or not (read/write or READ)
- OK email users enhance with ai not working
- OK user folders should move to a sub folder
- OK fix adding images
- OK Fix uploading artefacts
- OK export word needs to be reworked. I need to be able to export images and tables as well as good formatting
- OK format the exported pdf
- OK loading the artefact adds the images to the data zone!



## Discussion:
- make the tools sections collapsible
- Add the possibility to use multiple bindings at once with different configurations
- fix the return key not sending the message
- when cancelling the generation, refresh the discussion
- when the generation fails, refresh the discussion
- activate optional RAG for discussion datazone
- fix deleting a message deleting the whole sub children
- organize the discussion elements from recent to older with optional change of organization
- Extract discussion zone from chatview

### emailing system
- password reset views and fixing the lost password email problem


## services
- centralize icons management with a modal that allows preprocessing before building base64 png

  
## personalities
- Add personality sharing
- Revamp personalities management tools
- Add automatic generation of personalities
- Add rag for personality
- Add mcps for personality
- Add personality description to the list
- Add a system personalities management page for administrator
- Add personality maker AI
- FIx personality adding for users who are not admin ** IMPORTANT **
- Edit system prompt button
  
### bindings/models
- add alias for models


## user settings
- add activating realtime dms to the ui
  
## Rag settings 
- add RAG vectorizer setting to the user RAG settings
- add fast rag to the discussion

## cosmetics
- add customization of the webui
- add themes


## mcps
- change refresh mcps to reload mcps
- refresh mcps must be converted to reload mcps
- add protection for MCP output

## background processes
- add purge to tasks
- add a new cleaning of unused uploaded files task
- add adding rag stores files to tasks management with access to file upload status.
- reload mcps
- starting apps

## apps
- add the possibility to use the domain name not just localhost
- set the domain name globally so that it can be used eaésily
- only show active apps in the apps list

- ### todoooo: fix embed function to use a specific model
- add current processes listing
- add a cleaning cron

## integrate lollms apps

## Scratchpad
- add summerize document to scratchpad ** IMPORTANT **
- fix the scratchpad loop ** IMPORTANT **

## tasks management
- verify task update on remote machines

## data zones
- handle the case where the datazone is tempy
- add :
-   convert to document
-   save document to md (in docs list)

## installer
- add docker option
- build docker image


- add clear models button to admin interface
- if the model does not support image input, do not remove the image list in discussion zone, just make sure you deactivate any image in that list

# Multi workers optimization
Use REDIS instead of the polling mechanism (optional)

# URGENT:
add more details about the source chunks
add queuing for audio generation
revamp the mermaid ui to (accept the use of parenthesis inside brackets) and support comments
Fix the zooming and exporting of the mermaid diagram

