function get_pr_status() {
  gh pr status
}

for dir in ~/Fauna/*/; do
    cd $dir
    get_pr_status
done
