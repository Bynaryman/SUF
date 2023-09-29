# def replace_placeholders(input_file_path, output_file_path, placeholder_dict):
#     """
#     Read content from input_file_path, replace the placeholders with the values from
#     placeholder_dict and write the modified content to output_file_path.
#
#     :param input_file_path: Path to the file containing placeholders.
#     :param output_file_path: Path to save the file with placeholders replaced.
#     :param placeholder_dict: Dictionary of placeholders and their corresponding replacements.
#     """
#
#     # Read content from the input file
#     with open(input_file_path, 'r') as file:
#         content = file.read()
#
#     # Replace the placeholders
#     for placeholder, value in placeholder_dict.items():
#         content = content.replace(placeholder, value)
#
#     # Write the modified content to the output file
#     with open(output_file_path, 'w') as file:
#         file.write(content)

def replace_placeholders(input_file_path, output_file_path, *placeholder_dicts):
    """
    Read content from input_file_path, replace the placeholders with the values from
    placeholder_dicts and write the modified content to output_file_path.

    :param input_file_path: Path to the file containing placeholders.
    :param output_file_path: Path to save the file with placeholders replaced.
    :param placeholder_dicts: One or more dictionaries of placeholders and their corresponding replacements.
    """

    # Read content from the input file
    with open(input_file_path, 'r') as file:
        content = file.read()

    # Iterate through each provided dictionary and replace the placeholders
    for p_dict in placeholder_dicts:
        for placeholder, value in p_dict.items():
            content = content.replace(placeholder, value)

    # Write the modified content to the output file
    with open(output_file_path, 'w') as file:
        file.write(content)

