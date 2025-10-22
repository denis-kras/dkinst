from dkinst.cli import main  # the function named by the entry point
if __name__ == "__main__":
    import sys
    sys.argv = ["dkinst", "install", "mongodb"]
    main()
