# How to add comments to a Schemata file

You can add comments to a Schemata file by placing them between `/*` and `*/`, as shown below.

``` 
/* 
To do: add subelement 'author'.
*/

element book {
    attributes: id;
    allowedContent: [ title, subtitle (optional), isbn ];
}
```