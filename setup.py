from cx_Freeze import setup, Executable

setup(
    name="Control_Me",
    version="1.0.1",
    description="Control_Me",
    options={
        'build_exe': {
            'include_files': ['icon.ico'],  # Include the icon file
        }
    },
    executables=[Executable("main.py", 
                            base="Win32GUI", 
                            icon="icon.ico", 
                            target_name="Control_Me.exe" ,
                            shortcut_name="Control_Me")],
)
