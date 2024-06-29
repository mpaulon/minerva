# Minerva - simple blog engine

## Use pagefind as local search engine
 - Download the right pagefind binary [here](https://github.com/CloudCannon/pagefind/releases)
 - Extract it to the `tool` directory
 - Run `minerva --folder example build --clean && ./tools/pagefind_extended --site example/build --serve` 

## Project state

### TODO
 - add support of multiple languages
 - add authors list
 - add rss support
 - command line create new post

### IN PROGRESS
 - render simple index page (title, owner, description)
 - render simple post (title, description, date, author, content)
 - nice theme
 - search in page https://pagefind.app/docs/api/

### DONE
