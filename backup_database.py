#!/usr/bin/env python3
"""
Automatic SQLite Database Backup Script
Creates timestamped backups of cofind.db

Usage:
  python backup_database.py                    # Create single backup
  python backup_database.py --schedule daily   # Schedule daily backups (Windows Task Scheduler)
"""
import sqlite3
import os
import shutil
from datetime import datetime
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), 'cofind.db')
BACKUP_DIR = os.path.join(os.path.dirname(__file__), 'backups')

def create_backup():
    """Create a backup of the database"""
    
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database tidak ditemukan: {DB_PATH}")
        return False
    
    # Create backup directory if not exists
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
        print(f"Created backup directory: {BACKUP_DIR}")
    
    # Generate backup filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f'cofind_backup_{timestamp}.db'
    backup_path = os.path.join(BACKUP_DIR, backup_filename)
    
    try:
        # Copy database file
        shutil.copy2(DB_PATH, backup_path)
        
        # Verify backup
        backup_size = os.path.getsize(backup_path)
        original_size = os.path.getsize(DB_PATH)
        
        if backup_size == original_size:
            print("\n" + "="*70)
            print("DATABASE BACKUP SUCCESS")
            print("="*70)
            print(f"Original: {DB_PATH}")
            print(f"Backup:   {backup_path}")
            print(f"Size:     {backup_size:,} bytes ({backup_size/1024:.2f} KB)")
            print(f"Time:     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("="*70)
            
            # Clean old backups (keep last 7 days)
            clean_old_backups(keep_days=7)
            
            return True
        else:
            print("ERROR: Backup verification failed - file size mismatch")
            return False
            
    except Exception as e:
        print(f"ERROR: Backup failed - {str(e)}")
        return False

def clean_old_backups(keep_days=7):
    """Remove backups older than keep_days"""
    
    if not os.path.exists(BACKUP_DIR):
        return
    
    now = datetime.now()
    removed_count = 0
    
    for filename in os.listdir(BACKUP_DIR):
        if filename.startswith('cofind_backup_') and filename.endswith('.db'):
            filepath = os.path.join(BACKUP_DIR, filename)
            file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
            age_days = (now - file_time).days
            
            if age_days > keep_days:
                try:
                    os.remove(filepath)
                    print(f"Removed old backup: {filename} (age: {age_days} days)")
                    removed_count += 1
                except Exception as e:
                    print(f"Failed to remove {filename}: {str(e)}")
    
    if removed_count > 0:
        print(f"\nCleaned {removed_count} old backup(s)")

def list_backups():
    """List all available backups"""
    
    if not os.path.exists(BACKUP_DIR):
        print("No backups directory found")
        return
    
    backups = []
    for filename in os.listdir(BACKUP_DIR):
        if filename.startswith('cofind_backup_') and filename.endswith('.db'):
            filepath = os.path.join(BACKUP_DIR, filename)
            file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
            file_size = os.path.getsize(filepath)
            backups.append({
                'filename': filename,
                'path': filepath,
                'time': file_time,
                'size': file_size
            })
    
    if not backups:
        print("No backups found")
        return
    
    # Sort by time (newest first)
    backups.sort(key=lambda x: x['time'], reverse=True)
    
    print("\n" + "="*70)
    print("AVAILABLE BACKUPS")
    print("="*70)
    for i, backup in enumerate(backups, 1):
        age = (datetime.now() - backup['time']).days
        print(f"{i}. {backup['filename']}")
        print(f"   Time: {backup['time'].strftime('%Y-%m-%d %H:%M:%S')} ({age} days ago)")
        print(f"   Size: {backup['size']:,} bytes ({backup['size']/1024:.2f} KB)")
        print()
    print("="*70)

def restore_backup(backup_filename):
    """Restore database from backup"""
    
    backup_path = os.path.join(BACKUP_DIR, backup_filename)
    
    if not os.path.exists(backup_path):
        print(f"ERROR: Backup not found: {backup_path}")
        return False
    
    # Create safety backup of current database before restore
    print("Creating safety backup of current database...")
    safety_backup = f'cofind_pre_restore_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
    shutil.copy2(DB_PATH, os.path.join(BACKUP_DIR, safety_backup))
    print(f"Safety backup created: {safety_backup}")
    
    try:
        # Restore backup
        shutil.copy2(backup_path, DB_PATH)
        print("\n" + "="*70)
        print("DATABASE RESTORE SUCCESS")
        print("="*70)
        print(f"Restored from: {backup_filename}")
        print(f"Current database replaced")
        print("="*70)
        return True
    except Exception as e:
        print(f"ERROR: Restore failed - {str(e)}")
        return False

def create_windows_task():
    """Create Windows Task Scheduler task for daily backups"""
    
    script_path = os.path.abspath(__file__)
    python_exe = sys.executable
    
    task_xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>2024-01-01T02:00:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Actions>
    <Exec>
      <Command>{python_exe}</Command>
      <Arguments>{script_path}</Arguments>
    </Exec>
  </Actions>
</Task>
"""
    
    task_file = os.path.join(os.path.dirname(__file__), 'backup_task.xml')
    with open(task_file, 'w', encoding='utf-16') as f:
        f.write(task_xml)
    
    print("\n" + "="*70)
    print("WINDOWS TASK SCHEDULER SETUP")
    print("="*70)
    print("Task definition file created: backup_task.xml")
    print("\nTo schedule daily backups:")
    print("1. Open Task Scheduler (taskschd.msc)")
    print("2. Click 'Import Task...'")
    print(f"3. Select: {task_file}")
    print("4. Configure trigger time and save")
    print("\nOr run this command as Administrator:")
    print(f'schtasks /create /tn "COFIND Database Backup" /xml "{task_file}"')
    print("="*70)

def main():
    """Main function"""
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'list':
            list_backups()
        elif command == 'restore' and len(sys.argv) > 2:
            restore_backup(sys.argv[2])
        elif command == 'schedule':
            create_windows_task()
        elif command == 'help':
            print("\nUsage:")
            print("  python backup_database.py              # Create backup")
            print("  python backup_database.py list         # List all backups")
            print("  python backup_database.py restore <filename>")
            print("  python backup_database.py schedule     # Setup Windows scheduled task")
            print()
        else:
            print("Unknown command. Use 'help' for usage.")
    else:
        # Default: create backup
        create_backup()

if __name__ == '__main__':
    main()
