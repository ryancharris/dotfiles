---
description: Copy the latest assistant response to the system clipboard
---
Copy your most recent response to the system clipboard using `pbcopy`.

## Steps

1. Identify the full text of your most recent response (everything you just output to the user).
2. Run the following shell command, passing the text via stdin:

   ```
   pbcopy << 'EOF'
   <your latest response here>
   EOF
   ```

3. Confirm to the user that the output has been copied to the clipboard.
