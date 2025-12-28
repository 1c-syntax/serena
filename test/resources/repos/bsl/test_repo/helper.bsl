// Helper module with utility functions

Function HelperFunction() Export
    Return "Helper function was called.";
EndFunction

Function ProcessData(Data) Export
    If Data = Undefined Then
        Return "No data provided";
    EndIf;
    
    Return "Processed: " + Data;
EndFunction
