import json
from pathlib import Path


def merge_json_files(article_file_path, language, parse_dir_path, output_file_path):
    # Ensure parse directory exists
    parse_dir = Path(parse_dir_path)
    if not parse_dir.exists():
        raise FileNotFoundError(f"Parse directory {parse_dir_path} does not exist")

    # Read the main article.json file
    try:
        with open(article_file_path, 'r', encoding='utf-8') as f:
            articles = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Article file {article_file_path} not found")
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON in {article_file_path}")

    # List to store articles with valid hash files
    valid_articles = []

    # Process each article
    for article in articles:
        hash_value = article.get('hash')
        if not hash_value:
            print(f"Warning: Article missing hash value: {article.get('title', 'Unknown')}")
            continue

        # Construct path to hash-specific JSON file
        hash_file_path = parse_dir / f"{hash_value}_{language}.json"

        # Check if hash file exists
        if not hash_file_path.exists():
            print(f"Warning: No parse file found for hash {hash_value} at {hash_file_path}")
            continue

        # Read and merge the hash-specific JSON file
        try:
            with open(hash_file_path, 'r', encoding='utf-8') as f:
                parse_data = json.load(f)
                # Merge parse_data into article
                article.update(parse_data)
                # Add to valid articles list
                valid_articles.append(article)
        except json.JSONDecodeError:
            print(f"Warning: Invalid JSON in {hash_file_path}")
        except Exception as e:
            print(f"Error processing {hash_file_path}: {str(e)}")

    # Save the merged data to output file
    try:
        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(valid_articles, f, indent=4, ensure_ascii=False)
        print(f"Merged data saved to {output_file_path} with {len(valid_articles)} articles")
    except Exception as e:
        raise Exception(f"Failed to save output file: {str(e)}")

# Example usage
if __name__ == "__main__":
    article_file = "quantum_articles.json"
    language = "en"
    parse_dir = "parse"
    output_file = "documents-data.json"

    try:
        merge_json_files(article_file, language, parse_dir, output_file)
    except Exception as e:
        print(f"Error: {str(e)}")