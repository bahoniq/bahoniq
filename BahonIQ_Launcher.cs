using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Windows.Forms;

internal static class BahonIQLauncher
{
    [STAThread]
    private static void Main()
    {
        string root = AppDomain.CurrentDomain.BaseDirectory;
        string launcher = Path.Combine(root, "launcher.pyw");
        string log = Path.Combine(root, "BahonIQ_exe_launcher_error.log");
        try
        {
            if (!File.Exists(launcher))
                throw new FileNotFoundException("Не найден launcher.pyw рядом с BahonIQ.exe", launcher);

            string pythonw = FindPythonw();
            if (pythonw == null)
                throw new Exception("Python 3.14 не найден. Установите Python 3.14 с pythonw.exe или проверьте команду py -3.14.");

            var info = new ProcessStartInfo();
            info.FileName = pythonw;
            info.Arguments = "\"" + launcher + "\"";
            info.WorkingDirectory = root;
            info.UseShellExecute = false;
            info.CreateNoWindow = true;
            Process.Start(info);
        }
        catch (Exception ex)
        {
            try { File.AppendAllText(log, DateTime.Now.ToString("s") + " " + ex + Environment.NewLine, Encoding.UTF8); }
            catch { }
            MessageBox.Show("Не удалось запустить BahonIQ.\n\n" + ex.Message + "\n\nЖурнал: " + log,
                "BahonIQ — ошибка запуска", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    private static string FindPythonw()
    {
        try
        {
            var info = new ProcessStartInfo("py.exe", "-3.14 -c \"import sys; print(sys.executable)\"");
            info.UseShellExecute = false;
            info.RedirectStandardOutput = true;
            info.RedirectStandardError = true;
            info.CreateNoWindow = true;
            using (var process = Process.Start(info))
            {
                string output = process.StandardOutput.ReadToEnd().Trim();
                if (!process.WaitForExit(10000)) { try { process.Kill(); } catch { } return null; }
                if (process.ExitCode == 0 && File.Exists(output))
                {
                    string pythonw = Path.Combine(Path.GetDirectoryName(output), "pythonw.exe");
                    if (File.Exists(pythonw)) return pythonw;
                }
            }
        }
        catch { }
        string local = Environment.GetEnvironmentVariable("LOCALAPPDATA") ?? "";
        string[] candidates = {
            Path.Combine(local, "Programs", "Python", "Python314", "pythonw.exe"),
            @"C:\Python314\pythonw.exe",
            @"C:\Program Files\Python314\pythonw.exe"
        };
        foreach (string candidate in candidates)
            if (File.Exists(candidate)) return candidate;
        return null;
    }
}
