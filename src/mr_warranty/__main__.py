from mr_warranty.pipelines.main import main

if __name__ == "__main__":
    import sys
    # Soporta llamada como python -m mr_warranty [sqis|salesforce|ambos]
    # Reenvía args a main() si se proveen
    if len(sys.argv) > 1:
        # pipelines.main maneja argparse, dejar que lo haga
        from mr_warranty.pipelines.main import main as _main
        _main(sys.argv[1] if len(sys.argv) == 2 else "ambos")
    else:
        main()
