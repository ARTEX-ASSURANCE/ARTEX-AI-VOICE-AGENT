#!/usr/bin/env python3
"""
Script to detect duplicate function names in your LiveKit agent project
and provide solutions to fix the duplicate function name error.
"""

import os
import ast
import re
from collections import defaultdict
from typing import Dict, List, Set

class FunctionAnalyzer(ast.NodeVisitor):
    def __init__(self):
        self.functions = []
        self.decorators = []
    
    def visit_FunctionDef(self, node):
        # Check if function has decorators that might indicate it's a tool
        tool_decorators = []
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                tool_decorators.append(decorator.id)
            elif isinstance(decorator, ast.Attribute):
                tool_decorators.append(f"{decorator.attr}")
        
        self.functions.append({
            'name': node.name,
            'line': node.lineno,
            'decorators': tool_decorators,
            'is_tool': any(dec in ['tool', 'llm_tool', 'function_tool'] for dec in tool_decorators)
        })
        
        self.generic_visit(node)

def analyze_python_file(filepath: str) -> Dict:
    """Analyze a Python file for function definitions."""
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            content = file.read()
        
        tree = ast.parse(content)
        analyzer = FunctionAnalyzer()
        analyzer.visit(tree)
        
        return {
            'filepath': filepath,
            'functions': analyzer.functions,
            'content': content
        }
    except Exception as e:
        print(f"Error analyzing {filepath}: {e}")
        return {'filepath': filepath, 'functions': [], 'content': ''}

def find_duplicate_functions(project_path: str) -> Dict[str, List]:
    """Find all Python files and analyze them for duplicate function names."""
    function_registry = defaultdict(list)
    
    # Find all Python files in the project
    python_files = []
    for root, dirs, files in os.walk(project_path):
        # Skip virtual environment and cache directories
        dirs[:] = [d for d in dirs if d not in ['venv', '__pycache__', '.git', 'node_modules']]
        
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    print(f"Found {len(python_files)} Python files to analyze...")
    
    # Analyze each file
    for filepath in python_files:
        analysis = analyze_python_file(filepath)
        
        for func in analysis['functions']:
            function_registry[func['name']].append({
                'file': filepath,
                'line': func['line'],
                'decorators': func['decorators'],
                'is_tool': func['is_tool']
            })
    
    return function_registry

def generate_fixes(duplicates: Dict[str, List]) -> List[str]:
    """Generate specific fixes for duplicate function names."""
    fixes = []
    
    for func_name, occurrences in duplicates.items():
        if len(occurrences) > 1:
            fixes.append(f"\n🔍 DUPLICATE FUNCTION: '{func_name}' found in {len(occurrences)} places:")
            
            for i, occ in enumerate(occurrences):
                fixes.append(f"   {i+1}. {occ['file']}:{occ['line']} - Decorators: {occ['decorators']}")
            
            # Suggest specific renames based on file context
            fixes.append(f"\n💡 SUGGESTED FIXES for '{func_name}':")
            
            for i, occ in enumerate(occurrences):
                filename = os.path.basename(occ['file']).replace('.py', '')
                
                # Generate contextual name suggestions
                if 'auto' in occ['file'].lower():
                    suggested_name = f"{func_name}_auto"
                elif 'property' in occ['file'].lower():
                    suggested_name = f"{func_name}_property"
                elif 'health' in occ['file'].lower():
                    suggested_name = f"{func_name}_health"
                elif 'api' in occ['file'].lower():
                    suggested_name = f"{func_name}_api"
                elif filename != 'api':
                    suggested_name = f"{func_name}_{filename}"
                else:
                    suggested_name = f"{func_name}_{i+1}"
                
                fixes.append(f"   - In {occ['file']}:{occ['line']} → Rename to: '{suggested_name}'")
            
            fixes.append("-" * 60)
    
    return fixes

def create_fix_script(duplicates: Dict[str, List], project_path: str) -> str:
    """Create a Python script to automatically fix the duplicates."""
    
    script_content = '''#!/usr/bin/env python3
"""
Auto-generated script to fix duplicate function names in your LiveKit agent project.
Review the changes before running this script!
"""

import os
import re

def fix_duplicate_functions():
    """Fix duplicate function names by renaming them."""
    
    fixes_applied = []
    
'''
    
    for func_name, occurrences in duplicates.items():
        if len(occurrences) > 1:
            for i, occ in enumerate(occurrences[1:], 1):  # Skip first occurrence
                filename = os.path.basename(occ['file']).replace('.py', '')
                
                if 'auto' in occ['file'].lower():
                    new_name = f"{func_name}_auto"
                elif 'property' in occ['file'].lower():
                    new_name = f"{func_name}_property"
                elif 'health' in occ['file'].lower():
                    new_name = f"{func_name}_health"
                elif 'api' in occ['file'].lower():
                    new_name = f"{func_name}_api"
                elif filename != 'api':
                    new_name = f"{func_name}_{filename}"
                else:
                    new_name = f"{func_name}_{i}"
                
                script_content += f'''
    # Fix {func_name} in {occ['file']}
    try:
        with open(r"{occ['file']}", 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace function definition
        pattern = r'(def\\s+){func_name}(\\s*\\()'
        replacement = r'\\g<1>{new_name}\\g<2>'
        content = re.sub(pattern, replacement, content)
        
        with open(r"{occ['file']}", 'w', encoding='utf-8') as f:
            f.write(content)
        
        fixes_applied.append("Renamed {func_name} to {new_name} in {occ['file']}")
        print(f"✅ Renamed {func_name} to {new_name} in {occ['file']}")
        
    except Exception as e:
        print(f"❌ Error fixing {occ['file']}: {{e}}")
'''
    
    script_content += '''
    
    print(f"\\n🎉 Applied {len(fixes_applied)} fixes!")
    for fix in fixes_applied:
        print(f"  - {fix}")
    
    print("\\n⚠️  Remember to:")
    print("  1. Update any function calls to use the new names")
    print("  2. Update imports if these functions are imported elsewhere")
    print("  3. Test your application after making these changes")

if __name__ == "__main__":
    fix_duplicate_functions()
'''
    
    return script_content

def main():
    """Main function to analyze and provide fixes."""
    print("🔍 LiveKit Agent Duplicate Function Detector")
    print("=" * 50)
    
    # Get project path (current directory by default)
    project_path = input("Enter your project path (press Enter for current directory): ").strip()
    if not project_path:
        project_path = "."
    
    if not os.path.exists(project_path):
        print(f"❌ Path '{project_path}' does not exist!")
        return
    
    # Analyze functions
    print(f"\\nAnalyzing Python files in: {os.path.abspath(project_path)}")
    function_registry = find_duplicate_functions(project_path)
    
    # Find duplicates
    duplicates = {name: occurrences for name, occurrences in function_registry.items() 
                 if len(occurrences) > 1}
    
    if not duplicates:
        print("✅ No duplicate function names found!")
        return
    
    print(f"\\n🚨 Found {len(duplicates)} duplicate function name(s):")
    
    # Generate and display fixes
    fixes = generate_fixes(duplicates)
    for fix in fixes:
        print(fix)
    
    # Ask if user wants to generate auto-fix script
    generate_script = input("\\n❓ Generate automatic fix script? (y/n): ").lower().strip()
    
    if generate_script == 'y':
        fix_script = create_fix_script(duplicates, project_path)
        
        script_filename = "fix_duplicate_functions.py"
        with open(script_filename, 'w', encoding='utf-8') as f:
            f.write(fix_script)
        
        print(f"\\n✅ Auto-fix script saved as: {script_filename}")
        print("\\n⚠️  IMPORTANT: Review the script before running it!")
        print(f"   Run with: python {script_filename}")
    
    print("\\n📋 Manual Fix Summary:")
    print("1. Rename duplicate functions to have unique names")
    print("2. Update any references to the renamed functions")
    print("3. Ensure all tool functions have proper decorators")
    print("4. Test your application after making changes")

if __name__ == "__main__":
    main()