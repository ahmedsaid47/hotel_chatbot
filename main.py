import json
import re

def fix_json_file(file_path):
    """
    Fix the JSON syntax errors in the given file.
    The function reads the file, wraps all JSON objects in square brackets,
    adds commas between objects, and writes the fixed JSON back to the file.
    """
    print(f"Reading file: {file_path}")

    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()

        # Check if the content is already a valid JSON
        try:
            json.loads(content)
            print("File is already a valid JSON. No changes needed.")
            return True
        except json.JSONDecodeError:
            pass

        # Fix escape sequences in the content
        # Replace problematic escape sequences like \_ with _
        content = content.replace('\\_', '_')

        # Find all JSON objects in the file
        # Each object starts with { and ends with }}
        objects = re.findall(r'(\{.*?\}\})', content, re.DOTALL)

        if not objects:
            print("No JSON objects found in the file.")
            return False

        print(f"Found {len(objects)} JSON objects.")

        # Process each object to fix escape sequences
        fixed_objects = []
        for obj in objects:
            # Replace problematic escape sequences
            fixed_obj = obj.replace('\_', '_')
            # Replace doc\_type with doc_type, etc.
            fixed_obj = re.sub(r'\\([a-zA-Z])', r'\1', fixed_obj)
            fixed_objects.append(fixed_obj)

        # Create a valid JSON array by wrapping objects in square brackets and adding commas
        fixed_json = "[\n" + ",\n".join(fixed_objects) + "\n]"

        # Validate the fixed JSON
        try:
            json.loads(fixed_json)
            print("Fixed JSON is valid.")
        except json.JSONDecodeError as e:
            print(f"Error validating fixed JSON: {e}")
            # Try a different approach if the first one fails
            try:
                # Parse each object individually and then combine
                valid_objects = []
                for obj in fixed_objects:
                    try:
                        # Try to parse the object
                        parsed = json.loads(obj)
                        # If successful, add the properly formatted JSON
                        valid_objects.append(json.dumps(parsed, ensure_ascii=False))
                    except json.JSONDecodeError as obj_error:
                        print(f"Error in object: {obj_error}")
                        # Skip invalid objects
                        continue

                if not valid_objects:
                    print("No valid objects found.")
                    return False

                fixed_json = "[\n" + ",\n".join(valid_objects) + "\n]"
                # Validate the new fixed JSON
                json.loads(fixed_json)
                print("Fixed JSON is valid using alternative method.")
            except json.JSONDecodeError as alt_error:
                print(f"Error validating fixed JSON with alternative method: {alt_error}")
                return False

        # Write the fixed JSON back to the file
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(fixed_json)

        print(f"Successfully fixed JSON syntax in {file_path}")
        return True

    except Exception as e:
        print(f"Error fixing JSON file: {e}")
        return False

if __name__ == '__main__':
    json_file_path = "cullian_vector/data.json"
    fix_json_file(json_file_path)
