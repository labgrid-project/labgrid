# Splitting configuration into multiple yaml files

**TODO**:*write a coherent prose*


Essentially the files listed in `includes` are copy pasted into the "base" yaml with all the limitation it will cause.

Limitations:

* It is not allow to have multiple blocks with the same name. See the section 'Same block in multiple files'.
* Anchors must be defined before they are referenced. See the section 'Defining anchors'

## Same block in multiple files

This is not possible due to limitation in YAML. In the following example the `defaults` block from `first.yaml` will be overwritten with the `defaults` block from `second.yaml`

```yaml
# filename: first.yaml
defaults:
    foo: "hello"

includes:
    - "second.yaml"
```

```yaml
# filename: second.yaml
defaults:
    bar: "world"
```

The output produced by the **TODO***:name of this include functionality* will be

```yaml
# filename: first.yaml
defaults:
    foo: "hello"

# filename: second.yaml
defaults:
    bar: "world"
```

... which by YAML will be evaluated just as 

```yaml
defaults:
    bar: "world"
```

## Defining anchors

**TODO**: *actually this could be partly solved if the included files in dropped in where the include block in defined, and not just at the end of the base file*

Yaml dictates that anchors must be defines before they are referenced **TOD**:*insert reference*

```yaml
# filename: base.yaml
defines:
    target_ip: &target_ip
        "1.2.3.4"

includes:
    - "target.yaml"
```

```yaml
# filename: target.yaml
target:
    main:
        resources:
            - NetworkService:
                name: 'ssh'
                address: *target_ip
```

### How not to do it

This will not work because the included file is inserted at the bottom of `base.yaml`

```yaml
# filename: base.yaml
includes:
    - "hosts.yaml"

targe:
    main:
        resources:
            - NetworkService:
                name: 'ssh'
                address: *target_ip
```

```yaml
# filename: hosts.yaml
defines:
    target_ip: &target_ip
        "1.2.3.4"
```