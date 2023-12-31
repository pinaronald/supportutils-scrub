# scrubber/main.py

import sys
import os
from config import DEFAULT_CONFIG_PATH
from config_reader import ConfigReader
from ip_scrubber import IPScrubber
from domain_scrubber import DomainScrubber
from user_scrubber import UserScrubber
from hostname_scrubber import HostnameScrubber
from extractor import extract_supportconfig
from translator import Translator
from supportutils_scrub_logger import SupportutilsScrubLogger
from keyword_scrubber import KeywordScrubber

 
def process_file(file_path, config, ip_scrubber, domain_scrubber, user_scrubber, hostname_scrubber, logger:SupportutilsScrubLogger, verbose_flag, keyword_scrubber=None):
    """
    Process a supportconfig file, obfuscating sensitive information.

    Parameters:
    - file_path: Path to the supportconfig file.
    - config: Configuration file to enable various options.
    - ip_scrubber: Instance of IPScrubber.
    - domain_scrubber: Instance of DomainScrubber.
    - user_scrubber: Instance of UserScrubber.
    - hostname_scrubber: Instance of HostnameScrubber.
    - logger: Instance of SupportutilsScrubLogger. 
    - verbose_flag: Boolean indicating verbose output.

    Returns:
    - Tuple of dictionaries (ip_dict, domain_dict, user_dict, hostname_dict).
    """
    ip_dict = {}
    domain_dict = {}
    user_dict = {}
    hostname_dict = {}
    keyword_dict = {} 

    try:
        logger.info(f"Scrubbing file: {file_path}")
        with open(file_path, "r") as file:
            lines = file.readlines()

        # A switch to print a header if file was modified
        obfuscation_occurred = False

        for i, line in enumerate(lines):
            # Scrub IP addresses
            if config["obfuscate_ip"]:
                ip_list = IPScrubber.extract_ips(line)
                for ip in ip_list:
                    obfuscated_ip = ip_scrubber.scrub_ip(ip)  
                    ip_dict[ip] = obfuscated_ip
                    line = line.replace(ip, obfuscated_ip)
                    obfuscation_occurred = True

            # Scrub keywords
            #if True:
            if config.get('use_key_words_file', False) and keyword_scrubber:
                original_line = line
            #    #logger.info(f"Line:"+ line)
                line, line_keyword_dict = keyword_scrubber.scrub(line)  
                keyword_dict.update(line_keyword_dict) 
            #    logger.debug(f"Original: {original_line}, Scrubbed: {line}, Keywords Found: {line_keyword_dict}")

                if line != original_line:
                    obfuscation_occurred = True


            # Scrub keywords
            #if config.get('use_key_words_file', False) and keyword_scrubber:
            #    for i, line in enumerate(lines):
            #        original_line = line
            #        line, line_keyword_dict = keyword_scrubber.scrub(line)  
            #        keyword_dict.update(line_keyword_dict)  
            #        if line != original_line:
            #            obfuscation_occurred = True

            # Replace the line in the file with obfuscated content
            lines[i] = line

        # Write the changes back to the file
        with open(file_path, "w") as file:
            # Add a warning header if obfuscation occcured
            if obfuscation_occurred:
                file.write("#" + "-" * 93 + "\n")
                file.write("# WARNING: Sensitive information in this file has been obfuscated by supportutils-scrub.\n")
                file.write("#" + "-" * 93 + "\n\n")
            file.writelines(lines)

    except Exception as e:
        logger.error(f"Error processing file {file_path}: {str(e)}")

    return ip_dict, domain_dict, user_dict, hostname_dict, keyword_dict


def main():
    # Parse command-line arguments
    args = sys.argv[1:]
    supportconfig_path = args[0] if args else None
    config_path = args[args.index("--config") + 1] if "--config" in args else "/etc/supportutils-scrub.conf"
    verbose_flag = "--verbose" in args

    # Initialize the logger
    logger = SupportutilsScrubLogger(log_level="verbose" if verbose_flag else "normal")

    # Use the ConfigReader class to read the configuration
    config_reader = ConfigReader(DEFAULT_CONFIG_PATH)
    config = config_reader.read_config(config_path)
    logger.info(f"Config dictionary {config}")  # Remove, debuging only

    # Initialize scrubbers
    ip_scrubber = IPScrubber()
    domain_scrubber = DomainScrubber()
    user_scrubber = UserScrubber()
    hostname_scrubber = HostnameScrubber()
   
    # Conditional instantiation of KeywordScrubber
    if config.get('use_key_words_file', False):
        keyword_scrubber = KeywordScrubber(config['key_words_file'])
        keyword_scrubber.load_keywords()

        if not keyword_scrubber.is_loaded():
            logger.error("No keywords loaded. Check keyword file.")
            return
    else:
        keyword_scrubber = None
        logger.info("Keyword scrubbing not enabled.")


    # List of filenames to exclude from scrubbing
    exclude_files = ["memory.txt", "env.txt"]

    # Extract Supportconfig and get the list of report files
    report_files = extract_supportconfig(supportconfig_path)

    # Dictionaries to store obfuscation mappings
    total_ip_dict = {}
    total_domain_dict = {}
    total_user_dict = {}
    total_hostname_dict = {}
    total_keyword_dict = {}    

    for report_file in report_files:
        # Check if the current file should be excluded
        if os.path.basename(report_file) in exclude_files:
            logger.info(f"\x1b[33mSkipping file: {report_file} (Excluded)\x1b[0m")
            continue

        # Process with the report file
        ip_dict, domain_dict, user_dict, hostname_dict, keyword_dict = process_file(
            report_file, config, ip_scrubber, domain_scrubber, user_scrubber, hostname_scrubber, logger, verbose_flag, keyword_scrubber
        )

        # Aggregate the translation dictionaries
        total_ip_dict.update(ip_dict)
        total_domain_dict.update(domain_dict)
        total_user_dict.update(user_dict)
        total_hostname_dict.update(hostname_dict)
        total_keyword_dict.update(keyword_dict)

        # Print the translation dictionaries (for verbose output)
        if verbose_flag:
            logger.info("Obfuscation mappings in json output:")
            logger.info(f"IP mappings: {ip_dict}")
            logger.info(f"Domain mappings: {domain_dict}")
            logger.info(f"User mappings: {user_dict}")
            logger.info(f"Hostname mappings: {hostname_dict}")
            logger.info(f"Keyword mappings: {keyword_dict}")

            logger.info("-" * 20)


    # Save translation dictionaries to JSON files
    Translator.save_translation('ip_translation.json', total_ip_dict)
    Translator.save_translation('domain_translation.json', total_domain_dict)
    Translator.save_translation('user_translation.json', total_user_dict)
    Translator.save_translation('hostname_translation.json', total_hostname_dict)
    Translator.save_translation('keyword_translation.json', total_keyword_dict)  # Saving keyword translations


    if not verbose_flag:
        logger.info("Translation files saved.")

if __name__ == "__main__":
    main()

