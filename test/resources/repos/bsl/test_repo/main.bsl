// Main module for BSL Language Server tests
// This file contains a function that is called from other modules

Function Greet(Name) Export
    Return "Hello, " + Name + "!";
EndFunction

Function Add(A, B) Export
    Return A + B;
EndFunction

Procedure Main() Export
    UserName = "BSL User";
    Greeting = Greet(UserName);
    Message(Greeting);
    
    Result = Add(5, 3);
    Message(Result);
    
    HelperResult = HelperFunction();
    Message(HelperResult);
EndProcedure
