function open_in_github()
  local file_path = vim.fn.expand("%:p")

  local git_root = vim.fn.system("git -C " .. vim.fn.expand("%:p:h") .. " rev-parse --show-toplevel"):gsub("\n", "")

  if vim.v.shell_error ~= 0 then
    vim.notify("Not a git repository", vim.log.levels.ERROR)
    return
  end

  local relative_path = file_path:sub(#git_root + 2)

  local remote_url = vim.fn.system("git -C " .. git_root .. " config --get remote.origin.url"):gsub("\n", "")
  remote_url = remote_url:gsub("git@github.com:", "https://github.com/")
  remote_url = remote_url:gsub("%.git$", "")
  local commit_sha = vim.fn.system("git -C " .. git_root .. " rev-parse HEAD"):gsub("\n", "")
  local line_number = vim.api.nvim_win_get_cursor(0)[1]
  local github_url = string.format("%s/blob/%s/%s#L%d", remote_url, commit_sha, relative_path, line_number)

  local cmd
  if vim.fn.has("mac") == 1 then
    cmd = "open"
  elseif vim.fn.has("unix") == 1 then
    cmd = "xdg-open"
  elseif vim.fn.has("win32") == 1 then
    cmd = "start"
  end

  if cmd then
    vim.fn.system(cmd .. " " .. github_url)
    vim.notify("Opened in GitHub: " .. github_url, vim.log.levels.INFO)
  else
    vim.notify("Unsupported operating system", vim.log.levels.ERROR)
  end
end

return  {
    open_in_github = open_in_github
}
