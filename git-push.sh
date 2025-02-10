#!/usr/bin/env bash

if [[ "$#" -ne 2 ]]; then
    echo ": git-push.sh [branch] [message]"
    exit 1
fi


cp ./docs/updates.md README.md
git add .
git commit -m "$2"
git push origin $1
