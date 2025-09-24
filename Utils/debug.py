from dkinst.cli import main  # the function named by the entry point
if __name__ == "__main__":
    import sys
    # Simulate: dkinst install nodejs
    sys.argv = ["dkinst", "install", "nodejs"]
    main()
