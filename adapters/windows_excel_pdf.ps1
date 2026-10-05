param([Parameter(Mandatory=$true)][string]$InputPath,
      [Parameter(Mandatory=$true)][string]$OutputPath,
      [Parameter(Mandatory=$true)][string]$OwnerPath)
$ErrorActionPreference='Stop'
$owned=$null;$excel=$null;$book=$null;$native=$null;$code='converter_unavailable';$success=$false
try {
 $exe=$null
 foreach($key in @('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\excel.exe','HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\excel.exe')){
  if(Test-Path -LiteralPath $key){$candidate=(Get-Item -LiteralPath $key).GetValue('');if(Test-Path -LiteralPath $candidate){$exe=$candidate;break}}
 }
 if(-not $exe){throw 'Excel executable is not installed'}
 Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class ExcelPdfNative {
 delegate bool EnumProc(IntPtr hwnd, IntPtr data);
 [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc callback, IntPtr data);
 [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr hwnd, EnumProc callback, IntPtr data);
 [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint pid);
 [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetClassName(IntPtr hwnd, StringBuilder name, int size);
 [DllImport("oleacc.dll")] static extern int AccessibleObjectFromWindow(IntPtr hwnd, uint id, ref Guid iid, [MarshalAs(UnmanagedType.IDispatch)] out object result);
 public static object GetNativeWindow(int processId) {
  object found=null;
  EnumWindows((window,data)=>{
   uint pid;GetWindowThreadProcessId(window,out pid);if(pid!=processId)return true;
   EnumChildWindows(window,(child,ignored)=>{
    var name=new StringBuilder(128);GetClassName(child,name,name.Capacity);
    if(name.ToString()!="EXCEL7")return true;
    var iid=new Guid("00020400-0000-0000-C000-000000000046");object result;
    if(AccessibleObjectFromWindow(child,0xFFFFFFF0,ref iid,out result)==0){found=result;return false;}
    return true;
   },IntPtr.Zero);
   return found==null;
  },IntPtr.Zero);
  return found;
 }
}
'@
 $code='excel_launch_failed'
 # /x creates a separate instance. Its PID is known before any potentially blocking COM call.
 $owned=Start-Process -FilePath $exe -ArgumentList @('/x','/r',('"'+$InputPath+'"')) -WindowStyle Hidden -PassThru
 [pscustomobject]@{pid=$owned.Id;started=$owned.StartTime.ToUniversalTime().Ticks.ToString();executable=$exe} |
  ConvertTo-Json -Compress | Set-Content -LiteralPath $OwnerPath -Encoding utf8
 $code='com_start_failed'
 $deadline=[datetime]::UtcNow.AddSeconds(30)
 do {
  if($owned.HasExited){throw 'Owned Excel exited before opening the workbook'}
  $native=[ExcelPdfNative]::GetNativeWindow($owned.Id)
  if($native){break}
  Start-Sleep -Milliseconds 100
 } while([datetime]::UtcNow -lt $deadline)
 if(-not $native){throw 'Native Excel object unavailable'}
 $excel=$native.Application
 $excel.Visible=$false;$excel.DisplayAlerts=$false;$excel.AskToUpdateLinks=$false;$excel.AutomationSecurity=3
 $code='excel_open_failed'
 $book=$excel.ActiveWorkbook
 if(-not $book -or $book.FullName -ne $InputPath -or -not $book.ReadOnly){throw 'The owned workbook was not opened read-only'}
 $code='pdf_generation_failed'
 $sheet=$book.Worksheets.Item(([string][char]0x539f)+[char]0x672c)
 $sheet.ExportAsFixedFormat(0,$OutputPath,0,$false,$false)
 $code='output_missing'
 if(-not (Test-Path -LiteralPath $OutputPath)){throw 'PDF output missing'}
 $success=$true;$code='ok'
} catch {
 [Console]::Error.WriteLine('Excel PDF worker: '+$code+'; '+$_.Exception.GetType().FullName+'; HRESULT='+$_.Exception.HResult)
} finally {
 if($book){try{$book.Close($false)}catch{};[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($book);$book=$null}
 if($excel){try{$excel.Quit()}catch{};[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($excel);$excel=$null}
 if($native){[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($native);$native=$null}
 [GC]::Collect();[GC]::WaitForPendingFinalizers()
 if($owned){
  $live=Get-Process -Id $owned.Id -ErrorAction SilentlyContinue
  if($live -and $live.StartTime.ToUniversalTime().Ticks -eq $owned.StartTime.ToUniversalTime().Ticks){Stop-Process -Id $owned.Id -Force -ErrorAction SilentlyContinue}
 }
}
Write-Output ('PDF_RESULT='+([pscustomobject]@{ok=$success;code=$code}|ConvertTo-Json -Compress))
if(-not $success){exit 1}
