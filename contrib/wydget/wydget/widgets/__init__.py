from wydget.widgets.button import Button, TextButton, RepeaterButton
from wydget.widgets.frame import Frame, TabbedFrame
from wydget.widgets.drawer import Drawer
from wydget.widgets.label import Image, Label, XHTML
from wydget.widgets.menu import MenuItem, PopupMenu, DropDownMenu, DropDownItem
from wydget.widgets.movie import Movie
from wydget.widgets.selection import Selection, Option
from wydget.widgets.slider import VerticalSlider, HorizontalSlider
from wydget.widgets.slider import ArrowButtonUp, ArrowButtonDown
from wydget.widgets.slider import ArrowButtonLeft, ArrowButtonRight
from wydget.widgets.textline import  TextInput, PasswordInput
from wydget.widgets.checkbox import Checkbox
from wydget.widgets.table import Table, Heading, Row, Cell


from wydget import loadxml
for klass in [Frame, TabbedFrame,
        Drawer,
        Image, Label, XHTML,
        Button, TextButton, RepeaterButton,
        TextInput, PasswordInput,
        VerticalSlider, HorizontalSlider,
        ArrowButtonUp, ArrowButtonDown,
        ArrowButtonLeft, ArrowButtonRight,
        Checkbox,
        Movie,
        PopupMenu, MenuItem,
        DropDownMenu, DropDownItem,
        Selection, Option,
        Table, Heading, Row, Cell]:
    loadxml.xml_registry[klass.name] = klass

